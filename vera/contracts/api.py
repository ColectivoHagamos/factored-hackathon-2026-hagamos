"""Request and response bodies of the HTTP API /v1."""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Self, get_args

from pydantic import AwareDatetime, StringConstraints, model_validator

from vera.contracts.cases import Case
from vera.contracts.common import CandidateNumber, Contract, Identifier, Language, PolicyRuleId, ShortText
from vera.contracts.handoff import Action, Handoff, Queue, Transfer
from vera.contracts.legal import RouteId

MessageText = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
# The reasons of the opening menu: a button names one instead of the customer writing it.
Intent = Literal["unrecognized_charge", "improper_charge", "lost_card", "scam_transfer", "human_request"]
INTENTS: tuple[str, ...] = get_args(Intent)
# What a button sends back besides a candidate number: an answer, "not sure", or a reason of the menu.
OptionAnswer = Literal[
    "yes", "no", "not_sure", "unrecognized_charge", "improper_charge", "lost_card", "scam_transfer", "human_request"
]


class DemoSessionRequest(Contract):
    """Demo only: the customer is picked from the demo page; a document number never opens a session."""

    demo_customer: Identifier


class DemoSessionResponse(Contract):
    token: str
    expires_at: AwareDatetime


class StartConversationRequest(Contract):
    preferred_language: Language | None = None


class StartConversationResponse(Contract):
    conversation_id: Identifier
    greeting: str
    # The opening menu: the reasons VERA covers, as buttons; the customer may also write.
    options: tuple["Option", ...] = ()


class MessageRequest(Contract):
    text: MessageText | None = None
    # A candidate number, the answer to a question or a pending confirmation, or a reason of the opening menu.
    selected_option: CandidateNumber | OptionAnswer | None = None

    @model_validator(mode="after")
    def _exactly_one_input(self) -> Self:
        if (self.text is None) == (self.selected_option is None):
            raise ValueError("send either text or selected_option")
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


class MessageResponse(Contract):
    reply: str
    options: tuple[Option, ...] = ()
    # True when the customer may pick several options at once, as in the sweep.
    multiple_choice: bool = False
    pending_confirmation: PendingConfirmation | None = None
    glass_box: tuple[GlassBoxEntry, ...] = ()


class CaseView(Contract):
    case: Case
    legal_route: RouteId | None = None
    deadline: date | None = None
    actions: tuple[Action, ...] = ()


class QueueItem(Contract):
    """One conversation waiting for an analyst: a case handoff or a transfer note, for the console."""

    kind: Literal["case", "transfer"]
    reference: Identifier
    created_at: AwareDatetime
    queue: Queue
    summary: ShortText
    requires_pt_analyst: bool
    trace_id: Identifier

    @classmethod
    def of(cls, item: Handoff | Transfer) -> "QueueItem":
        transfer = isinstance(item, Transfer)
        return cls(
            kind="transfer" if transfer else "case",
            reference=item.transfer_id if transfer else item.case_id,
            created_at=item.created_at,
            queue=item.suggested_queue,
            summary=item.summary,
            requires_pt_analyst=item.requires_pt_analyst,
            trace_id=item.trace_id,
        )


class HealthResponse(Contract):
    status: Literal["ok", "degraded"]
    llm_provider: Identifier | None = None
    version: ShortText


class MetricsResponse(Contract):
    """Counters since the process started and recent latencies, for the analyst role (P54)."""

    interpreter: Identifier
    degraded: bool
    counts: dict[str, int]
    request_ms: dict[str, float | int | None]
    turn_ms: dict[str, float | int | None]
    # Calls, fallbacks, tokens and spending of the language model, when one is in use (P41).
    llm: dict[str, float | int] | None = None


class ApiErrorCode(StrEnum):
    UNAUTHORIZED = "unauthorized"
    # Same answer for a case of another customer and for a case that does not exist.
    NOT_FOUND = "not_found"
    CONFIRMATION_EXPIRED = "confirmation_expired"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


class ApiError(Contract):
    code: ApiErrorCode
    message: ShortText


StartConversationResponse.model_rebuild()
