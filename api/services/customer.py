"""What the bank's app shows the session customer: the profile with its cards, the recent movements and a case."""

from collections.abc import Callable
from datetime import datetime, timedelta

from pydantic import ValidationError

from api.failures import ApiFailure
from api.schemas import ApiErrorCode, CardView, CaseView, MeResponse, Movement
from api.services.demo import DemoDirectory
from vera.contracts.cases import Case
from vera.contracts.tools import ReadCaseInput
from vera.ports.bank import AnalystQueuePort, CardsPort, CustomersPort, TransactionsPort
from vera.ports.tools import Session, ToolsPort

# The movements the bank's app shows, so the person testing knows what to dispute.
MOVEMENTS_WINDOW = timedelta(days=180)
MOVEMENTS_LIMIT = 50


class CustomerViews:
    def __init__(
        self,
        *,
        customers: CustomersPort,
        cards: CardsPort,
        transactions: TransactionsPort,
        tools: ToolsPort,
        handoffs: AnalystQueuePort,
        now: Callable[[], datetime],
        demo: DemoDirectory,
    ) -> None:
        self._customers = customers
        self._cards = cards
        self._transactions = transactions
        self._tools = tools
        # The handoff of a case carries its legal route and the bank's next deadline.
        self._handoffs = handoffs
        self._now = now
        self._demo = demo

    def profile(self, customer_ref: str) -> MeResponse:
        customer = self._customers.customer(customer_ref)
        if customer is None:
            raise ApiFailure(ApiErrorCode.NOT_FOUND)
        persona = self._demo.people()[customer.customer_ref]
        cards = tuple(
            CardView(
                masked=card.masked_card,
                type="credit" if "credit" in card.card_type.lower() else "debit",
                status="blocked" if card.status == "blocked" else "active",
            )
            for card in self._cards.cards(customer.customer_ref)
        )
        return MeResponse(
            display_name=persona.display_name,
            first_name=persona.first_name,
            alias=customer.alias,
            country=customer.country,
            segment=customer.segment,
            language=persona.language,
            cards=cards,
        )

    def movements(self, customer_ref: str) -> list[Movement]:
        """The customer's movements, newest first: what the bank's app would show before a dispute."""
        until = self._now()
        masked = {card.card_ref: card.masked_card for card in self._cards.cards(customer_ref)}
        charges = self._transactions.charges(customer_ref, until - MOVEMENTS_WINDOW, until)
        newest = sorted(charges, key=lambda charge: charge.occurred_at, reverse=True)[:MOVEMENTS_LIMIT]
        return [
            Movement(
                occurred_at=charge.occurred_at,
                kind=charge.kind,
                merchant=charge.merchant or None,
                city=charge.city or None,
                country=charge.country_code or None,
                amount=charge.amount,
                currency=charge.currency,
                status=charge.status,
                card=masked.get(charge.card_ref) if charge.card_ref else None,
            )
            for charge in newest
        ]

    def case(self, customer_ref: str, case_id: str) -> CaseView:
        """A case of the session customer; another customer's case answers like one that does not exist."""
        try:
            query = ReadCaseInput(case_id=case_id)
        except ValidationError as error:
            raise ApiFailure(ApiErrorCode.NOT_FOUND) from error
        found = self._tools.read_case(Session(customer_ref, ""), query)
        if not isinstance(found, Case):
            raise ApiFailure(ApiErrorCode.NOT_FOUND)
        handoff = self._handoffs.handoff_of(case_id)
        deadline = next((o.due for o in handoff.legal_clock.obligations if o.due), None) if handoff else None
        return CaseView(case=found, legal_route=handoff.legal_clock.route if handoff else None, deadline=deadline)
