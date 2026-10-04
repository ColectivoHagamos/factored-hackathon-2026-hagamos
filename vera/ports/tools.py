"""Port of the agent tools, as the conversation flow sees them, and the values they exchange."""

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel

from vera.contracts.cases import Case
from vera.contracts.charges import ChargeDetail
from vera.contracts.handoff import Handoff, Transfer
from vera.contracts.interpretation import ClaimType
from vera.contracts.tools import (
    BlockCardInput,
    CreateHandoffInput,
    CreateTransferInput,
    ReadCaseInput,
    RegisterDisputeInput,
    SearchChargesInput,
    SearchChargesOutput,
    SendFraudAlertInput,
    SweepChargesInput,
    SweepChargesOutput,
    ToolError,
    ViewChargeInput,
)
from vera.ports.bank import CustomerRecord


@dataclass(frozen=True)
class Session:
    customer_ref: str
    conversation_id: str


@dataclass(frozen=True)
class Offers:
    """Numbered options of one conversation: number to reference, for charges and for cards."""

    charges: dict[int, str] = field(default_factory=dict)
    cards: dict[int, str] = field(default_factory=dict)

    def with_charges(self, refs: list[str]) -> "Offers":
        return replace(self, charges=_numbered(self.charges, refs))

    def with_cards(self, refs: list[str]) -> "Offers":
        return replace(self, cards=_numbered(self.cards, refs))

    def number_of_card(self, card_ref: str | None) -> int | None:
        return next((n for n, ref in self.cards.items() if ref == card_ref), None)


def _numbered(current: dict[int, str], refs: list[str]) -> dict[int, str]:
    numbered = dict(current)
    known = set(numbered.values())
    for ref in refs:
        if ref not in known:
            numbered[len(numbered) + 1] = ref
            known.add(ref)
    return numbered


@dataclass(frozen=True)
class Confirmation:
    token: str
    tool: str
    expires_at: datetime


@dataclass(frozen=True)
class GateResult:
    output: BaseModel | ToolError
    read_back_matches: bool


class ToolsPort(Protocol):
    def customer(self, session: Session) -> CustomerRecord | None: ...

    def disputes_in_last_days(self, session: Session, days: int) -> int: ...

    def search_charges(
        self, session: Session, offers: Offers, args: SearchChargesInput
    ) -> tuple[SearchChargesOutput, Offers] | ToolError: ...

    def view_charge(self, session: Session, offers: Offers, args: ViewChargeInput) -> ChargeDetail | ToolError: ...

    def sweep_charges(
        self, session: Session, offers: Offers, args: SweepChargesInput
    ) -> tuple[SweepChargesOutput, Offers] | ToolError: ...

    def read_case(self, session: Session, args: ReadCaseInput) -> Case | ToolError: ...

    def confirm(self, session: Session, tool: str, arguments: BaseModel) -> Confirmation: ...

    def block_card(self, session: Session, offers: Offers, args: BlockCardInput) -> GateResult: ...

    def register_dispute(
        self, session: Session, offers: Offers, args: RegisterDisputeInput, claim_type: ClaimType
    ) -> GateResult: ...

    def create_handoff(self, session: Session, args: CreateHandoffInput, handoff: Handoff) -> GateResult: ...

    def create_transfer(self, session: Session, args: CreateTransferInput, note: Transfer) -> GateResult: ...

    def send_fraud_alert(self, session: Session, offers: Offers, args: SendFraudAlertInput) -> GateResult: ...
