"""Runner (P44): every case, three wordings, two systems: the keyword baseline and the learned classifier.

Each run starts from an empty state, so no case sees another one's case or block. The result of every run is
written to evaluation/results/<set>.json; the report reads it. Both systems face the same cases and wordings.

Usage: python -m evaluation.run [dev|heldout] [path to demo.duckdb]   (default: dev, $VERA_DEMO_DB)
"""

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from evaluation.cases import read
from evaluation.graders import Grade, grade
from evaluation.simulator import Charges, Customer

HERE = Path(__file__).parent
SYSTEMS = ("rules", "classifier")
VARIANTS = (0, 1, 2)


def run_case(case, variant: int, system: str, demo_db: Path, charges: Charges) -> Grade:
    customer = Customer(case, variant, system, demo_db, charges)
    transcript = customer.talk()
    return grade(case, transcript, customer.container, customer.conversation, charges)


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "dev"
    demo_db = Path(sys.argv[2] if len(sys.argv) > 2 else os.environ["VERA_DEMO_DB"])
    cases = read(HERE / "scenarios" / f"{which}.jsonl")
    charges = Charges(demo_db)
    results = {}
    for system in SYSTEMS:
        grades = [run_case(case, variant, system, demo_db, charges) for case in cases for variant in VARIANTS]
        results[system] = [asdict(g) for g in grades]
        passed = sum(g.passed for g in grades)
        unsafe = sum(bool(g.unsafe) for g in grades)
        print(f"{system:10} {passed}/{len(grades)} runs pass, {unsafe} unsafe")
    out = HERE / "results" / f"{which}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    print(f"Results: {out.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
