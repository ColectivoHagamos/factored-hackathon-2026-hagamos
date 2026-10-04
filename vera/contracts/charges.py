"""Charges shown to the customer as numbered candidates; the model never sees raw identifiers."""

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import model_validator

from vera.contracts.common import Amount, CandidateNumber, Contract, Currency, MaskedCard, ShortText


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
    is_known_merchant: bool = False

    @model_validator(mode="after")
    def _purchases_carry_a_card(self) -> Self:
        # In the dataset, purchases come only from cards; bank adjustments come from other products.
        if self.kind is ChargeKind.PURCHASE and self.card is None:
            raise ValueError("a purchase must reference a masked card")
        return self


class ChargeDetail(Candidate):
    fraud_score_band: FraudScoreBand
