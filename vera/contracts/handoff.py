"""Structured handoff to a human analyst; it never carries the raw transcript."""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, StringConstraints, model_validator

from vera.contracts.cases import DisputeReason
from vera.contracts.charges import Candidate, ChargeDetail, FraudScoreBand, check_exposure
from vera.contracts.common import (
    Amount,
    CaseId,
    Contract,
    Country,
    Identifier,
    Language,
    Money,
    PolicyRuleId,
    ShortText,
    TransferId,
)
from vera.contracts.interpretation import Answer, ClaimType, ContactChannel, DeclaredChannel
from vera.contracts.legal import Layer, Level, Party, RouteId, RuleId, RuleStatus, TermUnit

NetworkCode = Annotated[str, StringConstraints(pattern=r"^\d{2}\.\d{1,2}(\.\d)?$")]
PolicyVersion = Annotated[str, StringConstraints(pattern=r"^\d+\.\d+$")]


class LanguageVariant(StrEnum):
    """Register used with the customer: tu (MX), usted (CO), vos (AR), voce (PT)."""

    ES_MX = "es-MX"
    ES_CO = "es-CO"
    ES_AR = "es-AR"
    PT = "pt"


class Segment(StrEnum):
    BASIC = "basic"
    PLUS = "plus"
    PREMIUM = "premium"
    STUDENT = "student"


class Queue(StrEnum):
    FRAUD = "fraud"
    COMPLAINTS = "complaints"


class RuleResult(StrEnum):
    APPLIES = "applies"
    NOT_APPLICABLE = "not_applicable"
    EXPIRED = "expired"


class GoodwillCriterion(StrEnum):
    """The three criteria of policy section 11.1; all of them are required to flag a candidate."""

    FIRST_DISPUTE_IN_12_MONTHS = "first_dispute_in_12_months"
    VERIFIED_AMOUNT_AT_MOST_USD_100 = "verified_amount_at_most_usd_100"
    RECOGNIZED_OR_BANK_CHARGE = "recognized_or_bank_charge"


class VerifiedFacts(Contract):
    """Facts read from tools only."""

    charges: tuple[Candidate, ...] = Field(min_length=1)
    total_exposure: tuple[Money, ...]
    total_exposure_usd: Amount
    fraud_score_band: FraudScoreBand

    @model_validator(mode="after")
    def _exposure_counts_only_approved_charges(self) -> Self:
        check_exposure(self.charges, self.total_exposure)
        return self


class DeclaredFacts(Contract):
    """Facts stated by the customer and not verified by any tool."""

    channel: DeclaredChannel | None = None
    has_card: Answer = Answer.NOT_SAID
    was_in_country: Answer = Answer.NOT_SAID
    authorized_payment: Answer = Answer.NOT_SAID
    # The date in the customer's own words ("ayer"), and how a third party reached them in a scam (POL-10).
    date_text: ShortText | None = None
    contacted_by: ContactChannel | None = None


class Sweep(Contract):
    charges_reviewed: int = Field(ge=0)
    not_recognized: int = Field(ge=0)

    @model_validator(mode="after")
    def _not_recognized_within_reviewed(self) -> Self:
        if self.not_recognized > self.charges_reviewed:
            raise ValueError("not_recognized cannot exceed charges_reviewed")
        return self


class Action(Contract):
    action: Literal["block_card", "register_dispute"]
    result: Literal["ok", "failed"]
    read_back: bool


class RuleEvaluation(Contract):
    id: RuleId
    result: RuleResult
    status: RuleStatus | None = None
    # Date on which an early adopted rule becomes mandatory by law.
    in_force_from: date | None = None
    detail: ShortText | None = None

    @model_validator(mode="after")
    def _early_adoption_states_its_legal_date(self) -> Self:
        if self.status is RuleStatus.EARLY_ADOPTED and self.in_force_from is None:
            raise ValueError("an early adopted rule must state in_force_from")
        return self


class Obligation(Contract):
    party: Party
    what: ShortText
    due: date | None = None
    unit: TermUnit | None = None


class LegalClock(Contract):
    route: RouteId
    rules_evaluated: tuple[RuleEvaluation, ...]
    deadline_verified: bool
    obligations: tuple[Obligation, ...] = ()
    venues: tuple[ShortText, ...] = ()

    @model_validator(mode="after")
    def _dates_only_from_verified_rules(self) -> Self:
        # Without an executable N1 rule the route is recorded and passed on without a date.
        if not self.deadline_verified and any(o.due is not None for o in self.obligations):
            raise ValueError("an unverified deadline cannot carry a due date")
        return self


class NetworkClock(Contract):
    """Contractual card network deadline for the analyst only; never communicated as law."""

    network: ShortText
    layer: Literal[Layer.NETWORK] = Layer.NETWORK
    level: Level
    suggested_code: NetworkCode
    due: date
    note: ShortText


class GoodwillCandidate(Contract):
    flagged: bool = False
    criteria: tuple[GoodwillCriterion, ...] = ()
    reason: ShortText | None = None

    @model_validator(mode="after")
    def _flag_requires_all_criteria(self) -> Self:
        if self.flagged and (set(self.criteria) != set(GoodwillCriterion) or self.reason is None):
            raise ValueError("a goodwill candidate requires the three criteria and a reason")
        return self


class TransferReason(StrEnum):
    """Why a conversation went to a person without a case handoff; each reason is a rule."""

    PERSON_REQUESTED = "person_requested"  # POL-01
    COERCION = "coercion"  # POL-02
    NOT_UNDERSTOOD = "not_understood"  # POL-05
    REGULATOR = "regulator"  # POL-09
    SCAM_TRANSFER = "scam_transfer"  # POL-10
    TOOL_FAILURE = "tool_failure"  # POL-13
    TURN_LIMIT = "turn_limit"  # the cap of turns per conversation
    LOST_CARD = "lost_card"  # POL-06: a lost or stolen card without recent movements to identify it


def _check_language(language: Language, variant: LanguageVariant, requires_pt_analyst: bool) -> None:
    if requires_pt_analyst != (language is Language.PT):
        raise ValueError("requires_pt_analyst must match a Portuguese conversation")
    if (variant is LanguageVariant.PT) != (language is Language.PT):
        raise ValueError("variant must match the language")


class Handoff(Contract):
    # 2.1 adds rules_applied; a reader of 2.0 finds every field it knew.
    schema_version: Literal["handoff/2.1"] = "handoff/2.1"
    case_id: CaseId
    created_at: AwareDatetime
    summary: ShortText
    language: Language
    variant: LanguageVariant
    requires_pt_analyst: bool
    account_country: Country
    segment: Segment
    claim_type: ClaimType
    reason: DisputeReason
    response_level: Literal[1, 2, 3]
    verified_facts: VerifiedFacts
    declared_by_customer: DeclaredFacts
    sweep: Sweep | None = None
    actions: tuple[Action, ...] = ()
    legal_clock: LegalClock
    network_clock: NetworkClock | None = None
    risk_signals: tuple[ShortText, ...] = ()
    fraud_alert: bool = False
    goodwill_candidate: GoodwillCandidate = GoodwillCandidate()
    suggested_queue: Queue
    open_questions: tuple[ShortText, ...] = ()
    # Every policy rule that decided a step of the conversation, in the order it first applied.
    rules_applied: tuple[PolicyRuleId, ...] = ()
    policy_version: PolicyVersion
    trace_id: Identifier

    @model_validator(mode="after")
    def _portuguese_goes_to_a_portuguese_speaking_analyst(self) -> Self:
        _check_language(self.language, self.variant, self.requires_pt_analyst)
        return self


class Transfer(Contract):
    """A conversation that went to a person without a case handoff, with what is already known (POL-01).

    Like the handoff, it never carries the transcript: the charges come from tools, and the rest is what the
    customer declared, the actions read back and what the analyst still has to ask.
    """

    schema_version: Literal["transfer/1.0"] = "transfer/1.0"
    transfer_id: TransferId
    created_at: AwareDatetime
    reason: TransferReason
    summary: ShortText
    language: Language
    variant: LanguageVariant
    requires_pt_analyst: bool
    account_country: Country
    segment: Segment
    claim_type: ClaimType | None = None
    charges: tuple[ChargeDetail, ...] = ()
    declared_by_customer: DeclaredFacts = DeclaredFacts()
    actions: tuple[Action, ...] = ()
    # The action the customer had in front of it when the conversation was transferred; it was never run.
    pending_action_not_run: Literal["block_card", "register_dispute"] | None = None
    # A case registered earlier in the same conversation.
    case_id: CaseId | None = None
    risk_signals: tuple[ShortText, ...] = ()
    fraud_alert: bool = False
    rules_applied: tuple[PolicyRuleId, ...] = ()
    suggested_queue: Queue
    open_questions: tuple[ShortText, ...] = ()
    policy_version: PolicyVersion
    trace_id: Identifier

    @model_validator(mode="after")
    def _portuguese_goes_to_a_portuguese_speaking_analyst(self) -> Self:
        _check_language(self.language, self.variant, self.requires_pt_analyst)
        return self
