"""The conversation's contract: what the customer sends in a turn and what VERA answers.

The core produces these models and the HTTP API publishes them unchanged, so the web and any other channel read the
same reply: its options, a pending confirmation, the glass box, the stage of the dispute and the charge in question.
"""

from datetime import date, datetime
from typing import Annotated, Literal, Self, get_args

from pydantic import AwareDatetime, StringConstraints, model_validator

from vera.contracts.charges import ChargeStatus
from vera.contracts.common import (
    Amount,
    CandidateNumber,
    Contract,
    Currency,
    Identifier,
    MaskedCard,
    PolicyRuleId,
    ShortText,
)

MessageText = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
# The reasons of the opening menu: a button names one instead of the customer writing it.
Intent = Literal["unrecognized_charge", "improper_charge", "lost_card", "scam_transfer", "human_request"]
INTENTS: tuple[str, ...] = get_args(Intent)
# What a button sends back besides a candidate number: an answer, "not sure", or a reason of the menu.
OptionAnswer = Literal[
    "yes", "no", "not_sure", "unrecognized_charge", "improper_charge", "lost_card", "scam_transfer", "human_request"
]
# Where the dispute stands, in the five states of the brand: received, analysis, verification, result, resolved.
Stage = Literal["received", "analysis", "verification", "result", "resolved"]


class MessageRequest(Contract):
    text: MessageText | None = None
    # A candidate number, the answer to a question or a pending confirmation, or a reason of the opening menu.
    selected_option: CandidateNumber | OptionAnswer | None = None
    # The reason the customer pressed in the bank's app ("I do not recognize this movement") next to the text that
    # names the charge: the button says what kind of claim it is, the text says which charge.
    intent: Intent | None = None

    @model_validator(mode="after")
    def _exactly_one_input(self) -> Self:
        if (self.text is None) == (self.selected_option is None):
            raise ValueError("send either text or selected_option")
        if self.intent is not None and self.text is None:
            raise ValueError("intent goes with the text that names the charge")
        return self


class Option(Contract):
    n: CandidateNumber
    label: ShortText
    # Buttons that are not a candidate carry their answer; the client sends it back as selected_option.
    answer: OptionAnswer | None = None


class PendingConfirmation(Contract):
    action: Literal["block_card", "register_dispute"]
    summary: ShortText
    expires_at: AwareDatetime


class GlassBoxEntry(Contract):
    """Rule applied in a reply, with its source and, when a verified rule yields one, the deadline."""

    rule_id: PolicyRuleId
    source: ShortText
    deadline: date | None = None


class ChargeSummary(Contract):
    """The charge in question, read from the tools, for the panel beside the conversation."""

    merchant: ShortText | None = None
    city: ShortText | None = None
    amount: Amount
    currency: Currency
    occurred_at: datetime
    status: ChargeStatus
    card: MaskedCard | None = None


class MessageResponse(Contract):
    reply: str
    options: tuple[Option, ...] = ()
    # True when the customer may pick several options at once, as in the sweep.
    multiple_choice: bool = False
    pending_confirmation: PendingConfirmation | None = None
    glass_box: tuple[GlassBoxEntry, ...] = ()
    stage: Stage = "received"
    charge: ChargeSummary | None = None
    case_id: Identifier | None = None
