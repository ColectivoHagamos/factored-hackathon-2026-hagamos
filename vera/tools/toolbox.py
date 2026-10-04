"""The tools of the agent, scoped to the session customer and to the options offered in the conversation.

Charges and cards are shown as numbered options; a number keeps pointing to the same reference for the whole
conversation. Anything that was not offered, or belongs to another customer, reads as not found.
"""

import hashlib
from collections.abc import Callable
from datetime import datetime, time, timedelta
from decimal import Decimal

from vera.contracts.cases import Case, CaseStatus
from vera.contracts.charges import Candidate, ChargeDetail, ChargeStatus
from vera.contracts.common import Money
from vera.contracts.handoff import Handoff
from vera.contracts.interpretation import ClaimType
from vera.contracts.tools import (
    BlockCardInput,
    BlockCardOutput,
    CreateHandoffInput,
    CreateHandoffOutput,
    ReadCaseInput,
    RegisterDisputeInput,
    RegisterDisputeOutput,
    SearchChargesInput,
    SearchChargesOutput,
    SendFraudAlertInput,
    SendFraudAlertOutput,
    SweepChargesInput,
    SweepChargesOutput,
    ToolError,
    ToolErrorCode,
    ViewChargeInput,
)
from vera.policy.engine import exposure_usd
from vera.ports.bank import (
    CardRecord,
    CardsPort,
    CasesPort,
    ChargeRecord,
    FraudAlertRecord,
    RoutingPort,
    TransactionsPort,
)
from vera.ports.tools import Offers, Session

MAX_CANDIDATES = 10
SWEEP_DAYS = 120


class Toolbox:
    def __init__(
        self,
        transactions: TransactionsPort,
        cards: CardsPort,
        cases: CasesPort,
        routing: RoutingPort,
        usd_rates: dict,
        now: Callable[[], datetime],
    ) -> None:
        self._transactions = transactions
        self._cards = cards
        self._cases = cases
        self._routing = routing
        self._usd_rates = usd_rates
        self._now = now

    # Read tools

    def search_charges(
        self, session: Session, offers: Offers, args: SearchChargesInput
    ) -> tuple[SearchChargesOutput, Offers] | ToolError:
        since = datetime.combine(args.date_from, time.min)
        until = datetime.combine(args.date_to, time.max)
        found = [c for c in self._transactions.charges(session.customer_ref, since, until) if _matches(c, args, offers)]
        if not found:
            return ToolError(code=ToolErrorCode.NO_RESULTS)
        found = sorted(found, key=lambda charge: charge.occurred_at, reverse=True)[:MAX_CANDIDATES]
        offers = self._offer(offers, found)
        return SearchChargesOutput(candidates=tuple(self._candidate(c, offers) for c in found)), offers

    def view_charge(self, session: Session, offers: Offers, args: ViewChargeInput) -> ChargeDetail | ToolError:
        charge = self._offered_charge(session, offers, args.candidate_n)
        if charge is None:
            return ToolError(code=ToolErrorCode.NOT_FOUND)
        return ChargeDetail(**self._candidate(charge, offers).model_dump(), fraud_score_band=charge.fraud_score_band)

    def sweep_charges(
        self, session: Session, offers: Offers, args: SweepChargesInput
    ) -> tuple[SweepChargesOutput, Offers] | ToolError:
        """Charges of the same card since the first suspicious one, pending ones included."""
        first = self._offered_charge(session, offers, args.candidate_n)
        if first is None or first.card_ref is None:
            return ToolError(code=ToolErrorCode.NOT_FOUND)
        until = self._now()
        recent = self._transactions.charges(session.customer_ref, first.occurred_at, until)
        same_card = [c for c in recent if c.card_ref == first.card_ref]
        offers = self._offer(offers, same_card)
        return SweepChargesOutput(charges=tuple(self._candidate(c, offers) for c in same_card)), offers

    def read_case(self, session: Session, args: ReadCaseInput) -> Case | ToolError:
        case = self._cases.read(args.case_id, session.customer_ref)
        return case if case else ToolError(code=ToolErrorCode.NOT_FOUND)

    # Write tools: called only through the action gate, which checks the confirmation token.

    def block_card(self, session: Session, offers: Offers, args: BlockCardInput) -> BlockCardOutput | ToolError:
        card = self._offered_card(session, offers, args.card_n)
        if card is None:
            return ToolError(code=ToolErrorCode.NOT_FOUND)
        if card.status != "blocked":
            self._cards.block(card.card_ref, idempotency_key=args.confirmation_token)
        return BlockCardOutput()

    def card_status(self, session: Session, offers: Offers, card_n: int) -> str | None:
        card = self._offered_card(session, offers, card_n)
        return card.status if card else None

    def register_dispute(
        self, session: Session, offers: Offers, args: RegisterDisputeInput, claim_type: ClaimType
    ) -> RegisterDisputeOutput | ToolError:
        charges = [self._offered_charge(session, offers, n) for n in args.charges_n]
        if any(charge is None for charge in charges):
            return ToolError(code=ToolErrorCode.NOT_FOUND)
        refs = tuple(charge.charge_ref for charge in charges)
        existing = next((case_id for ref in refs if (case_id := self._cases.case_with_charge(ref))), None)
        if existing:
            stored = self._cases.read(existing, session.customer_ref)
            if stored is None or stored.conversation_id != session.conversation_id:
                return ToolError(code=ToolErrorCode.DUPLICATE, case_id=existing)
            # A retry in the same conversation returns the case already registered.
            return RegisterDisputeOutput(case_id=stored.case_id, total_exposure=stored.total_exposure)
        exposure = _exposure(charges)
        case = Case(
            case_id=self._cases.next_case_id(),
            conversation_id=session.conversation_id,
            status=CaseStatus.REGISTERED,
            claim_type=claim_type,
            reason=args.reason,
            declared_channel=args.declared_channel,
            charges=tuple(self._candidate(charge, offers) for charge in charges),
            total_exposure=exposure,
            total_exposure_usd=exposure_usd(exposure, self._usd_rates),
            created_at=self._now().astimezone(),
        )
        key = _key(session.conversation_id, *sorted(refs), args.reason)
        stored = self._cases.register(case, session.customer_ref, refs, idempotency_key=key)
        return RegisterDisputeOutput(case_id=stored.case_id, total_exposure=stored.total_exposure)

    def create_handoff(
        self, session: Session, args: CreateHandoffInput, handoff: Handoff
    ) -> CreateHandoffOutput | ToolError:
        if self._cases.read(args.case_id, session.customer_ref) is None or handoff.case_id != args.case_id:
            return ToolError(code=ToolErrorCode.NOT_FOUND)
        return CreateHandoffOutput(handoff_id=self._routing.hand_off(handoff, args.queue))

    def send_fraud_alert(
        self, session: Session, offers: Offers, args: SendFraudAlertInput
    ) -> SendFraudAlertOutput | ToolError:
        charges = [self._offered_charge(session, offers, n) for n in args.charges_n]
        foreign_case = args.case_id is not None and self._cases.read(args.case_id, session.customer_ref) is None
        if None in charges or foreign_case:
            return ToolError(code=ToolErrorCode.NOT_FOUND)
        alert = FraudAlertRecord(
            customer_ref=session.customer_ref,
            case_id=args.case_id,
            signals=args.signals,
            charge_refs=tuple(charge.charge_ref for charge in charges if charge),
            card_blocked=args.card_blocked,
        )
        return SendFraudAlertOutput(alert_id=self._routing.fraud_alert(alert))

    # Helpers

    def _offer(self, offers: Offers, charges: list[ChargeRecord]) -> Offers:
        offers = offers.with_charges([c.charge_ref for c in charges])
        return offers.with_cards([c.card_ref for c in charges if c.card_ref])

    def _candidate(self, charge: ChargeRecord, offers: Offers) -> Candidate:
        number = next(n for n, ref in offers.charges.items() if ref == charge.charge_ref)
        card = next((c for c in self._customer_cards(charge.customer_ref) if c.card_ref == charge.card_ref), None)
        return Candidate(
            n=number,
            kind=charge.kind,
            occurred_at=charge.occurred_at,
            amount=charge.amount,
            currency=charge.currency,
            merchant=charge.merchant,
            merchant_category=charge.merchant_category,
            city=charge.city,
            country=charge.country_code,
            status=charge.status,
            card=card.masked_card if card else None,
            card_type=card.card_type if card else None,
            card_n=offers.number_of_card(charge.card_ref),
            is_known_merchant=charge.is_known_merchant,
        )

    def _customer_cards(self, customer_ref: str) -> tuple[CardRecord, ...]:
        return self._cards.cards(customer_ref)

    def _offered_charge(self, session: Session, offers: Offers, n: int) -> ChargeRecord | None:
        ref = offers.charges.get(n)
        if ref is None:
            return None
        since = self._now() - timedelta(days=365 * 3)
        return next(
            (c for c in self._transactions.charges(session.customer_ref, since, self._now()) if c.charge_ref == ref),
            None,
        )

    def _offered_card(self, session: Session, offers: Offers, n: int) -> CardRecord | None:
        ref = offers.cards.get(n)
        return next((c for c in self._cards.cards(session.customer_ref) if c.card_ref == ref), None)


def _matches(charge: ChargeRecord, args: SearchChargesInput, offers: Offers) -> bool:
    if args.kind and charge.kind is not args.kind:
        return False
    if args.amount is not None and abs(charge.amount - args.amount) > max(
        Decimal("0.01"), args.amount * Decimal("0.01")
    ):
        return False
    if args.merchant and (charge.merchant is None or args.merchant.casefold() not in charge.merchant.casefold()):
        return False
    return not (args.card_n and offers.cards.get(args.card_n) != charge.card_ref)


def _exposure(charges: list[ChargeRecord]) -> tuple[Money, ...]:
    totals: dict = {}
    for charge in charges:
        if charge.status is ChargeStatus.APPROVED:
            totals[charge.currency] = totals.get(charge.currency, Decimal(0)) + charge.amount
    return tuple(Money(amount=amount, currency=currency) for currency, amount in sorted(totals.items()))


def _key(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]
