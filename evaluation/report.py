"""Report (P46): the official metrics of the challenge for the keyword baseline and the learned classifier.

Every rate carries its denominator and a 95 % Wilson interval. The measurement is offline: a scripted customer
talks to the real application in process; it is a simulation, not a measurement in production.

Usage: python -m evaluation.report [dev|heldout] [--label after]   (reads evaluation/results/<set>[-<label>].json)
"""

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from evaluation.cases import Case, read

HERE = Path(__file__).parent
DOCS = HERE.parent / "docs" / "evaluation"
SECURITY_ATTACKS = ("injection", "foreign_charge", "expired_session")
Z = 1.96


def wilson(successes: int, total: int) -> dict:
    if total == 0:
        return {"k": 0, "n": 0, "rate": None, "low": None, "high": None}
    p = successes / total
    center = (p + Z * Z / (2 * total)) / (1 + Z * Z / total)
    half = Z * math.sqrt(p * (1 - p) / total + Z * Z / (4 * total * total)) / (1 + Z * Z / total)
    return {
        "k": successes,
        "n": total,
        "rate": round(p, 4),
        "low": round(center - half, 4),
        "high": round(center + half, 4),
    }


def in_scope(case: Case) -> bool:
    """Claims VERA exists for; out-of-scope questions and the security attacks are measured apart."""
    return case.block != "out_of_scope" and case.attack not in SECURITY_ATTACKS


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def metrics(cases: dict[str, Case], runs: list[dict]) -> dict:
    scope = [r for r in runs if in_scope(cases[r["case_id"]])]
    resolved = [r for r in scope if r["passed"] and cases[r["case_id"]].expected.automatable and r["queue"] is None]
    by_case = defaultdict(list)
    for r in runs:
        by_case[r["case_id"]].append(r["passed"])
    escalation = Counter()
    for r in runs:
        expected, got = cases[r["case_id"]].expected.queue, r["queue"]
        if expected and not got:
            escalation["missed"] += 1
        elif got and not expected:
            escalation["unnecessary"] += 1
        elif got and expected and got != expected:
            escalation["wrong_queue"] += 1
        elif got and expected:
            escalation["correct"] += 1
    expected_transfers = sum(1 for r in runs if cases[r["case_id"]].expected.queue)
    turn_ms = [s * 1000 for r in runs for s in r["seconds_per_turn"]]
    conversation_ms = [sum(r["seconds_per_turn"]) * 1000 for r in runs]

    def grouped(key) -> dict:
        groups = defaultdict(list)
        for r in runs:
            groups[key(cases[r["case_id"]])].append(r["passed"])
        return {name: wilson(sum(values), len(values)) for name, values in sorted(groups.items())}

    return {
        "runs": len(runs),
        "cases": len(by_case),
        "pass_at_1": wilson(sum(r["passed"] for r in runs), len(runs)),
        "pass_hat_3": wilson(sum(all(v) for v in by_case.values()), len(by_case)),
        "cases_whose_result_changes_with_the_wording": sum(1 for v in by_case.values() if 0 < sum(v) < len(v)),
        "safe_automated_resolution": {
            **wilson(len(resolved), len(scope)),
            "attempted": wilson(sum(r["attempted"] for r in scope), len(scope)),
            "eligible_for_automation": sum(cases[r["case_id"]].expected.automatable for r in scope),
        },
        "containment": wilson(sum(r["queue"] is None for r in runs), len(runs)),
        # Customer effort: in-scope runs in which VERA had to ask the customer to explain again in free text.
        "explained_again": wilson(sum(r["explained_again"] > 0 for r in scope), len(scope)),
        "escalation": {
            "expected_transfers": expected_transfers,
            "correct": escalation["correct"],
            "missed": wilson(escalation["missed"], expected_transfers),
            "wrong_queue": escalation["wrong_queue"],
            "unnecessary": wilson(escalation["unnecessary"], len(runs) - expected_transfers),
        },
        "unsafe_outcomes": {
            **wilson(sum(bool(r["unsafe"]) for r in runs), len(runs)),
            "by_type": dict(Counter(kind for r in runs for kind in r["unsafe"])),
        },
        "efficiency": {
            "turn_ms_p50": round(percentile(turn_ms, 0.5), 1),
            "turn_ms_p95": round(percentile(turn_ms, 0.95), 1),
            "conversation_ms_p50": round(percentile(conversation_ms, 0.5), 1),
            "conversation_ms_p95": round(percentile(conversation_ms, 0.95), 1),
            "turns_p50": statistics.median(r["turns"] for r in runs),
            "turns_p95": percentile([r["turns"] for r in runs], 0.95),
            "cost_usd_per_attempted_case": 0.0,
            "cost_usd_per_safe_resolution": 0.0 if resolved else "not defined",
        },
        "by_block": grouped(lambda c: c.attack or c.block),
        "by_language": grouped(lambda c: c.language),
        "by_country": grouped(lambda c: c.country),
        "by_segment": grouped(lambda c: c.segment),
        "failed_checks": dict(Counter(check for r in runs for check in r["failed_checks"])),
    }


def share(value: dict) -> str:
    if value["rate"] is None:
        return "not defined"
    interval = f"{value['low'] * 100:.1f}–{value['high'] * 100:.1f}"
    return f"{value['rate'] * 100:.1f} % ({value['k']}/{value['n']}; 95 % CI {interval})"


def markdown(report: dict) -> str:
    systems = report["systems"]
    names = {"rules": "Keyword baseline", "classifier": "Learned classifier"}
    lines = [
        f"# Evaluation · {report['set']} set",
        "",
        f"{report['kind'].capitalize()}. Cases: {sum(report['cases_by_block'].values())}, "
        f"each run three times with three different wordings; {report['portuguese_share'] * 100:.0f} % in Portuguese. "
        f"SHA-256 of the cases: `{report['sha256_of_the_cases']}`.",
        "",
        "## Official metrics",
        "",
        "| Metric | " + " | ".join(names[s] for s in systems) + " |",
        "|---|" + "---|" * len(systems),
    ]

    def row(label: str, render) -> None:
        lines.append(f"| {label} | " + " | ".join(render(systems[s]) for s in systems) + " |")

    row("Safe automated resolution (all in-scope runs)", lambda m: share(m["safe_automated_resolution"]))
    row("Attempted automation (in-scope runs)", lambda m: share(m["safe_automated_resolution"]["attempted"]))
    row("Containment (no transfer)", lambda m: share(m["containment"]))
    row("Customer had to explain again (in-scope runs)", lambda m: share(m["explained_again"]))
    row("Missed transfers (of expected)", lambda m: share(m["escalation"]["missed"]))
    row("Unnecessary transfers (of not expected)", lambda m: share(m["escalation"]["unnecessary"]))
    row("Transfers to the wrong queue", lambda m: str(m["escalation"]["wrong_queue"]))
    row("Unsafe outcomes (all runs)", lambda m: share(m["unsafe_outcomes"]))
    row("Every check passed, per run (pass@1)", lambda m: share(m["pass_at_1"]))
    row("Every wording of a case passed (pass^3)", lambda m: share(m["pass_hat_3"]))
    row("Cases whose result changes with the wording", lambda m: str(m["cases_whose_result_changes_with_the_wording"]))
    row(
        "Latency per turn p50 / p95",
        lambda m: f"{m['efficiency']['turn_ms_p50']} / {m['efficiency']['turn_ms_p95']} ms",
    )
    row(
        "Latency per conversation p50 / p95",
        lambda m: f"{m['efficiency']['conversation_ms_p50']} / {m['efficiency']['conversation_ms_p95']} ms",
    )
    row(
        "Cost per attempted case / per safe resolution",
        lambda m: (
            f"US$ {m['efficiency']['cost_usd_per_attempted_case']:.2f} / "
            f"{m['efficiency']['cost_usd_per_safe_resolution']}"
        ),
    )
    for title, key in (
        ("By block", "by_block"),
        ("By language", "by_language"),
        ("By country", "by_country"),
        ("By segment", "by_segment"),
    ):
        lines += [
            "",
            f"## {title} (pass@1)",
            "",
            "| | " + " | ".join(names[s] for s in systems) + " |",
            "|---|" + "---|" * len(systems),
        ]
        for group in next(iter(systems.values()))[key]:
            lines.append(f"| {group} | " + " | ".join(share(systems[s][key][group]) for s in systems) + " |")
    lines += ["", "## Unsafe outcomes and failed checks", ""]
    for s in systems:
        unsafe = systems[s]["unsafe_outcomes"]["by_type"] or {"none": 0}
        failed = systems[s]["failed_checks"] or {"none": 0}
        lines.append(f"- **{names[s]}:** unsafe {unsafe}; failed checks {failed}.")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("set", nargs="?", default="dev", choices=("dev", "heldout"))
    parser.add_argument("--label", default="")
    arguments = parser.parse_args()
    which, name = arguments.set, arguments.set + (f"-{arguments.label}" if arguments.label else "")
    scenario = HERE / "scenarios" / f"{which}.jsonl"
    cases = {c.id: c for c in read(scenario)}
    results = json.loads((HERE / "results" / f"{name}.json").read_text(encoding="utf-8"))
    kind = "offline simulation: a scripted customer talks to the application in process; not production"
    if arguments.label:
        kind += f"; rerun '{arguments.label}', after fixes this set's failures informed, so not a clean held-out"
    report = {
        "set": name,
        "sha256_of_the_cases": hashlib.sha256(scenario.read_bytes()).hexdigest(),
        "cases_by_block": dict(sorted(Counter(c.attack or c.block for c in cases.values()).items())),
        "portuguese_share": round(sum(c.language == "pt" for c in cases.values()) / len(cases), 4),
        "kind": kind,
        "systems": {system: metrics(cases, runs) for system, runs in results.items()},
    }
    DOCS.mkdir(parents=True, exist_ok=True)
    out = DOCS / f"{name}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (DOCS / f"{name}.md").write_text(markdown(report), encoding="utf-8")
    for system, values in report["systems"].items():
        sar, unsafe = values["safe_automated_resolution"], values["unsafe_outcomes"]
        print(
            f"{system:10} pass@1 {values['pass_at_1']['rate']:.3f}  pass^3 {values['pass_hat_3']['rate']:.3f}  "
            f"safe automated resolution {sar['rate']:.3f}  containment {values['containment']['rate']:.3f}  "
            f"unsafe {unsafe['k']}/{unsafe['n']}  missed transfers {values['escalation']['missed']['k']}  "
            f"unnecessary {values['escalation']['unnecessary']['k']}"
        )
    print(f"Report: {out.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
