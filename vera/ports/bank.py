"""Ports to the bank systems: customers, transactions and cards (read), card control, cases and routing.

Records carry internal references; the tools translate them into numbered options before anything reaches the
conversation, so neither the customer nor the model ever handles a reference.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from vera.contracts.cases import Case
from vera.contracts.charges import ChargeKind, ChargeStatus, FraudScoreBand
from vera.contracts.common import Country, Currency
from vera.contracts.handoff import Handoff, Queue, Transfer


@dataclass(frozen=True)
class CustomerRecord:
    customer_ref: str
    alias: str
    country: Country
    segment: str
    age_band: str | None
    # Acceptance scenarios the demo customer was chosen for, such as A1; empty in production.
    scenarios: tuple[str, ...] = ()


@dataclass(frozen=True)
class CardRecord:
    card_ref: str
    customer_ref: str
    card_type: str
    masked_card: str
    status: str


@dataclass(frozen=True)
class ChargeRecord:
    charge_ref: str
    customer_ref: str
    card_ref: str | None
    kind: ChargeKind
    occurred_at: datetime
    amount: Decimal
    currency: Currency
    amount_usd: Decimal
    merchant: str | None
    merchant_category: str | None
    city: str | None
    country_code: str | None
    status: ChargeStatus
    fraud_score_band: FraudScoreBand
    is_known_merchant: bool


class CustomersPort(Protocol):
    def customer(self, customer_ref: str) -> CustomerRecord | None: ...

    def customers(self) -> tuple[CustomerRecord, ...]: ...


class TransactionsPort(Protocol):
    def charges(self, customer_ref: str, since: datetime, until: datetime) -> tuple[ChargeRecord, ...]:
        """Purchases and bank adjustments of one customer, oldest first."""
        ...

    def disputes_since(self, customer_ref: str, since: datetime) -> int: ...


class CardsPort(Protocol):
    def cards(self, customer_ref: str) -> tuple[CardRecord, ...]: ...

    def block(self, card_ref: str, idempotency_key: str) -> None:
        """Block the card; blocking a card that is already blocked succeeds."""
        ...


class CasesPort(Protocol):
    def register(self, case: Case, customer_ref: str, charge_refs: tuple[str, ...], idempotency_key: str) -> Case:
        """Store the case once per key; a repeated key returns the case stored the first time.

        The stored case may carry another case id than the one given: the store assigns it, so that two
        registrations at the same time never share one. Callers use the case returned.
        """
        ...

    def read(self, case_id: str, customer_ref: str) -> Case | None:
        """The case, only for its own customer: another customer's case reads as not found."""
        ...

    def case_with_charge(self, charge_ref: str) -> str | None: ...

    def next_case_id(self) -> str: ...


@dataclass(frozen=True)
class FraudAlertRecord:
    customer_ref: str
    case_id: str | None
    signals: tuple[str, ...]
    charge_refs: tuple[str, ...]
    card_blocked: bool


class RoutingPort(Protocol):
    def hand_off(self, handoff: Handoff, queue: Queue) -> str:
        """Deliver the handoff to an analyst queue and return its reference."""
        ...

    def fraud_alert(self, alert: FraudAlertRecord) -> str:
        """Deliver the alert to the Fraud team and return its reference."""
        ...

    def fraud_alerts_of(self, customer_ref: str) -> tuple[FraudAlertRecord, ...]: ...

    def transfer(self, note: Transfer, conversation_id: str) -> Transfer:
        """Deliver the note to an analyst queue once per conversation; the store assigns the transfer id."""
        ...


class AnalystQueuePort(Protocol):
    """What waits for an analyst: the queue, and each case handoff or transfer note by its reference."""

    def queue(self, limit: int = 50) -> tuple[Handoff | Transfer, ...]: ...

    def handoff_of(self, case_id: str) -> Handoff | None: ...

    def transfer_of(self, transfer_id: str) -> Transfer | None: ...
