"""Tests of the comparison between the executable policy and the master policy document."""

from scripts.check_policy import compare, master_ids_and_version
from vera.policy.model import load_policy

POLICY = load_policy()


def master_document(rule_ids: list[str], version: str) -> str:
    rows = "\n".join(f"| {rule_id} | condition | effect |" for rule_id in rule_ids)
    table = f"| Id | If | Then |\n|---|---|---|\n{rows}\n"
    return f"# Master policy\n\n{table}\n## Versions\n\n| {version} | 2026-10-03 | change |\n"


def test_identical_ids_and_version_pass():
    assert compare(POLICY, master_document(sorted(POLICY.ids), POLICY.version)) == []


def test_a_rule_missing_on_either_side_and_a_different_version_fail():
    ids = sorted(POLICY.ids - {"POL-16"}) + ["POL-18"]
    problems = compare(POLICY, master_document(ids, "1.5"))
    assert "only in the master policy: POL-18" in problems
    assert "only in the executable policy: POL-16" in problems
    assert any("version" in problem for problem in problems)


def test_latest_version_is_the_first_row_of_the_version_table():
    text = master_document(["POL-01"], "1.4") + "| 1.3 | 2026-10-02 | older |\n"
    assert master_ids_and_version(text) == (frozenset({"POL-01"}), "1.4")
