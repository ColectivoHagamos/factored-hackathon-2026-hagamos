"""Check that the executable policy is complete and, when available, identical in ids and version to the master policy.

The master policy document is kept outside this repository; its path is given in VERA_MASTER_POLICY.
Usage: python -m scripts.check_policy
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from vera.policy.engine import PolicyEngine
from vera.policy.model import Policy, load_policy

RULE_ROW = re.compile(r"^\| ((?:POL|PROH)-\d{2}) \|", re.MULTILINE)
VERSION_ROW = re.compile(r"^\| (\d+\.\d+) \| \d{4}-\d{2}-\d{2} \|", re.MULTILINE)


def master_ids_and_version(text: str) -> tuple[frozenset[str], str | None]:
    """Rule ids of the rule tables and the latest version of the version table of the master policy."""
    match = VERSION_ROW.search(text)
    return frozenset(RULE_ROW.findall(text)), match.group(1) if match else None


def compare(policy: Policy, master_text: str) -> list[str]:
    ids, version = master_ids_and_version(master_text)
    problems = [f"only in the master policy: {rule_id}" for rule_id in sorted(ids - policy.ids)]
    problems += [f"only in the executable policy: {rule_id}" for rule_id in sorted(policy.ids - ids)]
    if version != policy.version:
        problems.append(f"version {policy.version} differs from the master policy version {version}")
    return problems


def main() -> int:
    policy = load_policy()
    PolicyEngine(policy)
    print(f"OK  executable policy {policy.version}: {len(policy.rules)} rules with predicates")
    master = os.environ.get("VERA_MASTER_POLICY")
    if not master:
        print("SKIP  VERA_MASTER_POLICY is not set: comparison with the master policy not run")
        return 0
    problems = compare(policy, Path(master).read_text(encoding="utf-8"))
    for problem in problems:
        print(f"FAIL  {problem}")
    if not problems:
        print(f"OK  same ids and version as the master policy ({len(policy.ids)} ids)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
