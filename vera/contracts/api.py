"""Request and response bodies of the HTTP API /v1."""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, StringConstraints, model_validator

from vera.contracts.cases import Case
from vera.contracts.common import CandidateNumber, Contract, Identifier, Language, ShortText
from vera.contracts.handoff import Action
from vera.contracts.legal import RouteId

MessageText = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
PolicyRuleId = Annotated[str, StringConstraints(pattern=r"^((POL|PROH)-\d{2}|(CO|MX|AR|BR)-R\d{2})$")]


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


class MessageRequest(Contract):
    text: MessageText | None = None
    # A candidate number, or the answer to a pending confirmation.
    selected_option: CandidateNumber | Literal["yes", "no"] | None = None

    @model_validator(mode="after")
    def _exactly_one_input(self) -> Self:
        if (self.text is None) == (self.selected_option is None):
            raise ValueError("send either text or selected_option")
        return self


class Option(Contract):
    n: CandidateNumber
    label: ShortText
    # Yes-or-no buttons carry their answer; the client sends it back as selected_option.
    answer: Literal["yes", "no"] | None = None


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


class HealthResponse(Contract):
    status: Literal["ok", "degraded"]
    llm_provider: Identifier | None = None
    version: ShortText


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
