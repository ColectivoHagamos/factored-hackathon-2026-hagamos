"""Charges shown to the customer as numbered candidates; the model never sees raw identifiers."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import model_validator

from vera.contracts.common import Amount, CandidateNumber, Contract, Currency, MaskedCard, Money, ShortText


class ChargeKind(StrEnum):
    PURCHASE = "purchase"
    BANK_ADJUSTMENT = "bank_adjustment"


class ChargeStatus(StrEnum):
    APPROVED = "approved"
    PENDING = "pending"
    DECLINED = "declined"
    REVERSED = "reversed"


class FraudScoreBand(StrEnum):
    """Band of the dataset fraud score; the raw score and the fraud label never leave the adapter."""

    AT_MOST_30 = "<=30"
    ABOVE_30 = ">30"
    NONE = "none"


class Candidate(Contract):
    n: CandidateNumber
    kind: ChargeKind
    occurred_at: datetime
    amount: Amount
    currency: Currency
    merchant: ShortText | None = None
    merchant_category: ShortText | None = None
    city: ShortText | None = None
    country: ShortText | None = None
    status: ChargeStatus
    card: MaskedCard | None = None
    card_type: Literal["credit", "debit"] | None = None
    # Number of the card among the options of the conversation, for block_card.
    card_n: CandidateNumber | None = None
    is_known_merchant: bool = False

    @model_validator(mode="after")
    def _purchases_carry_a_card(self) -> Self:
        # In the dataset, purchases come only from cards; bank adjustments come from other products.
        if self.kind is ChargeKind.PURCHASE and self.card is None:
            raise ValueError("a purchase must reference a masked card")
        return self


class ChargeDetail(Candidate):
    fraud_score_band: FraudScoreBand


def check_exposure(charges: Sequence[Candidate], total_exposure: Sequence[Money]) -> None:
    """Raise unless each charge appears once and the exposure is the sum of approved charges per currency."""
    numbers = [charge.n for charge in charges]
    if len(numbers) != len(set(numbers)):
        raise ValueError("each charge must appear once")
    currencies = [money.currency for money in total_exposure]
    if len(currencies) != len(set(currencies)):
        raise ValueError("total_exposure must have one entry per currency")
    # Pending or declined charges stay for follow-up or as signals, never as disputed amount.
    expected: defaultdict[Currency, Decimal] = defaultdict(Decimal)
    for charge in charges:
        if charge.status is ChargeStatus.APPROVED:
            expected[charge.currency] += charge.amount
    if {money.currency: money.amount for money in total_exposure} != dict(expected):
        raise ValueError("total_exposure must equal the sum of approved charges per currency")
