"""State of a conversation between turns. It is stored with every reply event, so a replay rebuilds it."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from vera.contracts.handoff import LanguageVariant, Queue
from vera.contracts.interpretation import Answer, ClaimType, DeclaredChannel
from vera.policy.engine import Signal


class Step(StrEnum):
    ASK_CLAIM = "ask_claim"
    CHOOSE_CHARGE = "choose_charge"
    CLARIFY = "clarify"
    ASK_CHANNEL = "ask_channel"
    ASK_CARD = "ask_card"
    SWEEP = "sweep"
    CONFIRM_BLOCK = "confirm_block"
    CONFIRM_REGISTER = "confirm_register"
    # The reading of a request for a person was unsure, so VERA asked before transferring.
    CONFIRM_PERSON = "confirm_person"
    DONE = "done"
    HANDED_OFF = "handed_off"


class FlowState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: Step = Step.ASK_CLAIM
    variant: LanguageVariant
    claim_type: ClaimType | None = None
    charges_offered: dict[int, str] = {}
    cards_offered: dict[int, str] = {}
    chosen: int | None = None
    # Charges shown in the sweep: the only ones the customer can disown there.
    swept: list[int] = []
    disputed: list[int] = []
    declared_channel: DeclaredChannel | None = None
    has_card: Answer = Answer.NOT_SAID
    signals: list[Signal] = []
    # POL-16: the charges of a fraud alert that is due, and the alert once it was sent.
    fraud_alert_charges: list[int] = []
    fraud_alert_id: str | None = None
    attempts: int = 0
    pending_tool: str | None = None
    pending_arguments: dict | None = None
    case_id: str | None = None
    escalated: bool = False
    queue: Queue | None = None
    rules_applied: list[str] = []

    def advance(self, **changes: object) -> "FlowState":
        """A new state with the given changes; a new question starts its own count of attempts (POL-05)."""
        if changes.get("step", self.step) != self.step:
            changes.setdefault("attempts", 0)
        return FlowState.model_validate(self.model_dump() | changes)
