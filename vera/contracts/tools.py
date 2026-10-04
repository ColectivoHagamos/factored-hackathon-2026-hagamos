"""Inputs and outputs of the agent tools.

The customer always comes from the session, never from an argument, and the model only picks numbers
from options the server offered: no tool takes a raw identifier or an amount to act on.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from vera.contracts.cases import Case, DisputeReason
from vera.contracts.charges import Candidate, ChargeDetail, ChargeKind
from vera.contracts.common import Amount, CandidateNumber, CaseId, Contract, Identifier, Money, ShortText
from vera.contracts.handoff import Queue
from vera.contracts.interpretation import DeclaredChannel

ConfirmationToken = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{16,128}$")]


class ToolErrorCode(StrEnum):
    NO_RESULTS = "no_results"
    TIMEOUT = "timeout"
    NOT_FOUND = "not_found"
    INVALID_TOKEN = "invalid_token"
    DUPLICATE = "duplicate"
    INVALID_SCHEMA = "invalid_schema"
    FAILURE = "failure"


class ToolError(Contract):
    code: ToolErrorCode
    # A duplicate registration returns the case that already exists.
    case_id: CaseId | None = None

    @model_validator(mode="after")
    def _duplicate_returns_the_existing_case(self) -> Self:
        if (self.code is ToolErrorCode.DUPLICATE) != (self.case_id is not None):
            raise ValueError("case_id is returned only, and always, for a duplicate")
        return self


class SearchChargesInput(Contract):
    date_from: date
    date_to: date
    amount: Amount | None = None
    # What the customer named: it matches the merchant or the city of the charge ("un cargo en Madrid").
    merchant: ShortText | None = None
    card_n: CandidateNumber | None = None
    kind: ChargeKind | None = None

    @model_validator(mode="after")
    def _range_is_ordered(self) -> Self:
        if self.date_from > self.date_to:
            raise ValueError("date_from cannot be later than date_to")
        return self


class SearchChargesOutput(Contract):
    candidates: tuple[Candidate, ...]


class ViewChargeInput(Contract):
    candidate_n: CandidateNumber


class SweepChargesInput(Contract):
    """Charges of the same card since the first suspicious one, pending ones included."""

    candidate_n: CandidateNumber


class SweepChargesOutput(Contract):
    charges: tuple[Candidate, ...]


class BlockCardInput(Contract):
    card_n: CandidateNumber
    confirmation_token: ConfirmationToken


class BlockCardOutput(Contract):
    # Blocking a card that is already blocked is a success.
    status: Literal["blocked"] = "blocked"


class RegisterDisputeInput(Contract):
    charges_n: tuple[CandidateNumber, ...] = Field(min_length=1)
    reason: DisputeReason
    declared_channel: DeclaredChannel
    confirmation_token: ConfirmationToken

    @model_validator(mode="after")
    def _each_charge_once(self) -> Self:
        if len(self.charges_n) != len(set(self.charges_n)):
            raise ValueError("each charge must appear once")
        return self


class RegisterDisputeOutput(Contract):
    case_id: CaseId
    total_exposure: tuple[Money, ...]


class ReadCaseInput(Contract):
    case_id: CaseId


class CreateHandoffInput(Contract):
    case_id: CaseId
    queue: Queue


class CreateHandoffOutput(Contract):
    handoff_id: Identifier


class SendFraudAlertInput(Contract):
    """POL-16: an alert to the Fraud team with the signals, the charges and the block status, with or without a case.

    It is not the dispute handoff and decides nothing about money.
    """

    charges_n: tuple[CandidateNumber, ...] = Field(min_length=1)
    signals: tuple[ShortText, ...] = Field(min_length=1)
    card_blocked: bool
    case_id: CaseId | None = None


class SendFraudAlertOutput(Contract):
    alert_id: Identifier


# The seven tools of the design and the POL-16 alert. Moving or promising money is not a tool (PROH-03).
TOOL_INPUTS: dict[str, type[Contract]] = {
    "search_charges": SearchChargesInput,
    "view_charge": ViewChargeInput,
    "sweep_charges": SweepChargesInput,
    "block_card": BlockCardInput,
    "register_dispute": RegisterDisputeInput,
    "read_case": ReadCaseInput,
    "create_handoff": CreateHandoffInput,
    "send_fraud_alert": SendFraudAlertInput,
}

TOOL_OUTPUTS: dict[str, type[Contract]] = {
    "search_charges": SearchChargesOutput,
    "view_charge": ChargeDetail,
    "sweep_charges": SweepChargesOutput,
    "block_card": BlockCardOutput,
    "register_dispute": RegisterDisputeOutput,
    "read_case": Case,
    "create_handoff": CreateHandoffOutput,
    "send_fraud_alert": SendFraudAlertOutput,
}
