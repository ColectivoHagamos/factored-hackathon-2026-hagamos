"""Request and response bodies that only the HTTP API knows: access, demo sessions, the customer's views, the
analyst's queue, operations and errors. The conversation's own contract lives in vera/contracts/conversation.py."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints

from vera.contracts.cases import Case, DisputeReason
from vera.contracts.charges import ChargeKind, ChargeStatus
from vera.contracts.common import (
    Amount,
    Contract,
    Country,
    Currency,
    Identifier,
    Language,
    MaskedCard,
    ShortText,
)
from vera.contracts.conversation import Option
from vera.contracts.handoff import Action, Queue, TransferReason
from vera.contracts.interpretation import ClaimType
from vera.contracts.legal import RouteId


class LoginRequest(Contract):
    """The access to the demo, so nobody without an account spends the language model."""

    username: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class LoginResponse(Contract):
    token: str
    expires_at: AwareDatetime
    display_name: ShortText
    role: Literal["tester"]


class DemoCustomer(BaseModel):
    customer_ref: str
    # Invented, as the subset holds no names (api/personas.py).
    display_name: str
    first_name: str
    alias: str
    country: str
    segment: str
    scenarios: list[str]
    language: str


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
    options: tuple[Option, ...] = ()


class CardView(Contract):
    masked: MaskedCard
    type: Literal["credit", "debit"]
    status: Literal["active", "blocked"]


class MeResponse(Contract):
    """The demo customer as the bank's app would show it; the name is invented, as the subset holds none."""

    display_name: ShortText
    first_name: ShortText
    alias: ShortText
    country: Country
    segment: ShortText
    language: Language
    cards: tuple[CardView, ...] = ()


class Movement(Contract):
    """A movement of the session customer, newest first, so the person testing knows what to dispute."""

    occurred_at: datetime
    kind: ChargeKind
    merchant: ShortText | None = None
    city: ShortText | None = None
    country: ShortText | None = None
    amount: Amount
    currency: Currency
    status: ChargeStatus
    card: MaskedCard | None = None


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
    # The summary's parts as codes, so a console shows them in its own language instead of reading the summary.
    claim_type: ClaimType | None = None
    reason: DisputeReason | TransferReason
    charge_count: int = Field(ge=0)
    pending_action: Literal["block_card", "register_dispute"] | None = None


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


class SourceTable(Contract):
    """One table of the Factored dataset as the pipeline received it, with what its contracts let through."""

    name: Identifier
    rows_in: int = Field(ge=0)
    rows_valid: int = Field(ge=0)
    rows_quarantined: int = Field(ge=0)


class Count(Contract):
    label: Identifier
    count: int = Field(ge=0)


class DemoSubset(Contract):
    """The pseudonymized subset VERA runs on, counted live from the database: totals only, never a record."""

    customers: int = Field(ge=0)
    customers_by_country: tuple[Count, ...]
    cards: int = Field(ge=0)
    cards_by_status: tuple[Count, ...]
    movements: int = Field(ge=0)
    movements_by_kind: tuple[Count, ...]
    movements_by_status: tuple[Count, ...]
    earlier_disputes: int = Field(ge=0)
    first_movement: date | None = None
    last_movement: date | None = None
    customers_per_scenario: tuple[Count, ...] = ()


class DataOverview(Contract):
    """Where the data of the demo comes from and how much of it there is, for the page that shows it to a reviewer."""

    source_tables: tuple[SourceTable, ...]
    # SHA-256 of the manifest of the raw files the pipeline read: the same data gives the same hash.
    source_manifest: ShortText | None = None
    subset: DemoSubset
