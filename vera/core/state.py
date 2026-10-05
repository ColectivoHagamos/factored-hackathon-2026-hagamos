"""State of a conversation between turns. It is stored with every reply event, so a replay rebuilds it."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from vera.contracts.handoff import LanguageVariant, Queue
from vera.contracts.interpretation import Answer, ClaimType, ContactChannel, DeclaredChannel
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
    # POL-01: the customer asked for a person and VERA offered once to go on first.
    PERSON_OFFERED = "person_offered"
    # POL-10: VERA asked the key questions of a scam and waits for the answer before the transfer.
    SCAM_DETAILS = "scam_details"
    # A lost or stolen card: which card, when the customer has several, so it can be protected first.
    CHOOSE_CARD = "choose_card"
    # After the card is protected, the recent movements, so the customer marks the ones they did not make.
    REVIEW = "review"
    # A payment declined or a card blocked: VERA showed what it sees and offered the person who can unblock.
    BLOCKED_OFFER = "blocked_offer"
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
    # POL-10: the customer made the payment, deceived by a third party; when, in their words, and how they were reached.
    authorized_payment: Answer = Answer.NOT_SAID
    date_text: str | None = None
    contacted_by: ContactChannel | None = None
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
    # POL-01: offers made to go on before a transfer.
    person_offers: int = 0
    # The open question during a detour about a person (POL-01 offer, POL-14 check), to go back to it.
    resume_step: Step | None = None
    # Warm replies at the opening (a greeting, small talk, another topic), so the same words are never sent twice.
    nudges: int = 0
    # A lost or stolen card is protected before anything else; its recent movements are reviewed afterwards.
    review_after_block: bool = False
    # Times VERA validated the customer's emotion, so the words change each time.
    calmed: int = 0
    # An improper charge that is a purchase charged twice: the search looks at purchases, and the reason is duplicate.
    duplicate: bool = False

    def advance(self, **changes: object) -> "FlowState":
        """A new state with the given changes; a new question starts its own count of attempts (POL-05)."""
        if changes.get("step", self.step) != self.step:
            changes.setdefault("attempts", 0)
        return FlowState.model_validate(self.model_dump() | changes)
