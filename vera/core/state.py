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
    disputed: list[int] = []
    declared_channel: DeclaredChannel | None = None
    has_card: Answer = Answer.NOT_SAID
    signals: list[Signal] = []
    attempts: int = 0
    pending_tool: str | None = None
    pending_arguments: dict | None = None
    case_id: str | None = None
    escalated: bool = False
    queue: Queue | None = None
    rules_applied: list[str] = []

    def advance(self, **changes: object) -> "FlowState":
        """A new state with the given changes, validated like the original."""
        return FlowState.model_validate(self.model_dump() | changes)
