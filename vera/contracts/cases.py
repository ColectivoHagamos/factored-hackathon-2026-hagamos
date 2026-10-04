"""Dispute case as registered and read back."""

from collections import defaultdict
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, Field, model_validator

from vera.contracts.charges import Candidate, ChargeStatus
from vera.contracts.common import Amount, CaseId, Contract, Currency, Identifier, Money
from vera.contracts.interpretation import ClaimType, DeclaredChannel


class CaseStatus(StrEnum):
    REGISTERED = "registered"
    ESCALATED = "escalated"
    CLOSED = "closed"


class DisputeReason(StrEnum):
    FRAUD = "fraud"
    NOT_RECEIVED = "not_received"
    NOT_AS_DESCRIBED = "not_as_described"
    INCORRECT_AMOUNT = "incorrect_amount"
    DUPLICATE = "duplicate"
    CANCELLED_RECURRING = "cancelled_recurring"
    BANK_CHARGE = "bank_charge"
    RECOGNIZED_BY_CUSTOMER = "recognized_by_customer"


class Case(Contract):
    case_id: CaseId
    conversation_id: Identifier
    status: CaseStatus
    claim_type: ClaimType
    reason: DisputeReason
    declared_channel: DeclaredChannel
    charges: tuple[Candidate, ...] = Field(min_length=1)
    total_exposure: tuple[Money, ...]
    total_exposure_usd: Amount
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _exposure_counts_only_approved_charges(self) -> Self:
        # One case with the total amount of approved charges, per currency; pending ones stay for follow-up.
        numbers = [charge.n for charge in self.charges]
        if len(numbers) != len(set(numbers)):
            raise ValueError("each charge must appear once in a case")
        currencies = [money.currency for money in self.total_exposure]
        if len(currencies) != len(set(currencies)):
            raise ValueError("total_exposure must have one entry per currency")
        expected: defaultdict[Currency, Decimal] = defaultdict(Decimal)
        for charge in self.charges:
            if charge.status is ChargeStatus.APPROVED:
                expected[charge.currency] += charge.amount
        declared = {money.currency: money.amount for money in self.total_exposure}
        if declared != dict(expected):
            raise ValueError("total_exposure must equal the sum of approved charges per currency")
        return self
