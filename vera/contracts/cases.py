"""Dispute case as registered and read back."""

from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, Field, model_validator

from vera.contracts.charges import Candidate, check_exposure
from vera.contracts.common import Amount, CaseId, Contract, Identifier, Money
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
        check_exposure(self.charges, self.total_exposure)
        return self
