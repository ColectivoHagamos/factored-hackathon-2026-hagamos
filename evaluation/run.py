"""Runner (P44): every case, three wordings, two systems: the keyword baseline and the learned classifier.

Each run starts from an empty state, so no case sees another one's case or block. The result of every run is
written to evaluation/results/<set>.json; the report reads it. Both systems face the same cases and wordings.

Usage: python -m evaluation.run [dev|heldout] [--label after] [--demo-db path]   (default: dev, $VERA_DEMO_DB)
A label names a rerun apart, as the rerun of the held-out after the fixes it informed.
"""

import argparse
import json
import logging
import os
from dataclasses import asdict
from pathlib import Path

from evaluation.cases import read
from evaluation.graders import Grade, grade
from evaluation.simulator import Charges, Customer, load_phrases

HERE = Path(__file__).parent
SYSTEMS = ("rules", "classifier")
VARIANTS = (0, 1, 2)


def run_case(case, variant: int, system: str, demo_db: Path, charges: Charges, phrases: dict) -> Grade:
    customer = Customer(case, variant, system, demo_db, charges, phrases)
    transcript = customer.talk()
    return grade(case, transcript, customer.container, customer.conversation, charges)


def main() -> None:
    # The tool-failure attack makes the store fail on purpose; its warnings would bury the summary.
    logging.getLogger("vera.tools").setLevel(logging.ERROR)
    parser = argparse.ArgumentParser()
    parser.add_argument("set", nargs="?", default="dev", choices=("dev", "heldout"))
    parser.add_argument("--label", default="")
    parser.add_argument("--demo-db", default=os.environ.get("VERA_DEMO_DB"))
    arguments = parser.parse_args()
    which, demo_db = arguments.set, Path(arguments.demo_db)
    cases = read(HERE / "scenarios" / f"{which}.jsonl")
    charges, phrases = Charges(demo_db), load_phrases(which)
    results = {}
    for system in SYSTEMS:
        grades = [run_case(case, variant, system, demo_db, charges, phrases) for case in cases for variant in VARIANTS]
        results[system] = [asdict(g) for g in grades]
        passed = sum(g.passed for g in grades)
        unsafe = sum(bool(g.unsafe) for g in grades)
        print(f"{system:10} {passed}/{len(grades)} runs pass, {unsafe} unsafe")
    out = HERE / "results" / f"{which}{'-' + arguments.label if arguments.label else ''}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    print(f"Results: {out.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
