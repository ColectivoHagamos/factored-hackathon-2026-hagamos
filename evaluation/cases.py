"""Evaluation case: who the customer is, what the simulated customer does, and the final state expected.

A case holds only pseudonymous references to the demo subset and template names; merchants and amounts are read
from the subset when the case runs, so no dataset value is written into the repository.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

Block = Literal["normal", "clarification", "mitigation", "ambiguous", "human", "improper", "out_of_scope", "attack"]
Attack = Literal["injection", "foreign_charge", "expired_session", "tool_failure", "wrong_data", "multilingual"]
Queue = Literal["fraud", "complaints"]


class Script(BaseModel):
    """What the simulated customer does when VERA asks; anything not asked is never volunteered."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    opening: str
    recognizes_after_receipt: bool = False
    has_card: bool = True
    accepts_block: bool = False
    asks_for_a_person_at_receipt: bool = False
    session_expires_before_confirming: bool = False
    tools_fail: bool = False


class Expected(BaseModel):
    """Final state, labeled by construction from the policy, never from a run of the system."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_charges: tuple[str, ...] = ()
    blocked: bool = False
    queue: Queue | None = None
    security_event: bool = False
    fraud_alert: bool = False
    session_expired: bool = False
    # A case counts toward safe automated resolution only when it ends well without a person.
    automatable: bool = False


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    block: Block
    attack: Attack | None = None
    language: Literal["es", "pt"]
    country: str
    segment: str
    customer: str
    target: tuple[str, ...] = ()
    # Another customer, for the foreign-data attack; a charge of another customer names a merchant this one lacks.
    other_customer: str | None = None
    wrong_merchant_from: str | None = None
    script: Script
    expected: Expected


def read(path: Path) -> tuple[Case, ...]:
    return tuple(Case.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line)


def write(path: Path, cases: list[Case]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(case.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) for case in cases]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
