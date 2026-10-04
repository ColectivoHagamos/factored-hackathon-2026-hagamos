"""Builder of the structured handoff for the analyst. Verified facts come only from tools; the transcript never goes."""

from datetime import datetime

from vera.contracts.cases import Case
from vera.contracts.charges import ChargeDetail, FraudScoreBand
from vera.contracts.common import Language
from vera.contracts.handoff import (
    Action,
    DeclaredFacts,
    GoodwillCandidate,
    Handoff,
    LanguageVariant,
    LegalClock,
    NetworkClock,
    Obligation,
    Queue,
    RuleEvaluation,
    RuleResult,
    Segment,
    Sweep,
    Transfer,
    TransferReason,
    VerifiedFacts,
)
from vera.contracts.interpretation import ClaimType
from vera.contracts.legal import Level
from vera.core.legal_route import LegalAssessment, network_code, network_due
from vera.ports.bank import CustomerRecord

UNVERIFIED = "literal text pending verification: informed without a date"
# The store assigns the transfer id when it keeps the note, as it does with case ids.
PENDING_TRANSFER_ID = "TRF-000000"
CARD_LAST_SEEN = "When did the customer last see the card?"
# What the analyst still has to find out, by the reason of the transfer.
OPEN_QUESTIONS: dict[TransferReason, tuple[str, ...]] = {
    TransferReason.PERSON_REQUESTED: (),
    TransferReason.COERCION: ("Is the customer safe to talk now, and through which channel?",),
    TransferReason.NOT_UNDERSTOOD: ("What happened, and which charge or account does the customer mean?",),
    TransferReason.REGULATOR: ("What has the customer filed, or wants to file, with the regulator?",),
    TransferReason.SCAM_TRANSFER: ("How much was transferred, and to which account or person?",),
    TransferReason.TOOL_FAILURE: ("The bank records could not be read: which charge does the customer mean?",),
    TransferReason.TURN_LIMIT: ("What does the customer still need? The conversation did not converge.",),
}


def build_handoff(
    *,
    case: Case,
    customer: CustomerRecord,
    variant: LanguageVariant,
    response_level: int,
    fraud_score_band: FraudScoreBand,
    declared: DeclaredFacts,
    sweep: Sweep | None,
    actions: tuple[Action, ...],
    legal: LegalAssessment,
    risk_signals: tuple[str, ...],
    fraud_alert: bool,
    goodwill: GoodwillCandidate,
    queue: Queue,
    open_questions: tuple[str, ...],
    policy_version: str,
    created_at: datetime,
) -> Handoff:
    language = Language.PT if variant is LanguageVariant.PT else Language.ES
    first = min(case.charges, key=lambda charge: charge.occurred_at)
    summary = f"{case.claim_type.value.replace('_', ' ')}: {len(case.charges)} charge(s), reason {case.reason.value}"
    return Handoff(
        case_id=case.case_id,
        created_at=created_at,
        summary=summary,
        language=language,
        variant=variant,
        requires_pt_analyst=language is Language.PT,
        account_country=customer.country,
        segment=Segment(customer.segment),
        claim_type=case.claim_type,
        reason=case.reason,
        response_level=response_level,
        verified_facts=VerifiedFacts(
            charges=case.charges,
            total_exposure=case.total_exposure,
            total_exposure_usd=case.total_exposure_usd,
            fraud_score_band=fraud_score_band,
        ),
        declared_by_customer=declared,
        sweep=sweep,
        actions=actions,
        legal_clock=_legal_clock(legal),
        network_clock=NetworkClock(
            network="Visa (assumed from the BIN)",
            level=Level.N2,
            suggested_code=network_code(case.reason, declared.channel),
            due=network_due(first.occurred_at),
            note="contractual network rule, not law; verify with the network rules through the issuer",
        ),
        risk_signals=risk_signals,
        fraud_alert=fraud_alert,
        goodwill_candidate=goodwill,
        suggested_queue=queue,
        open_questions=open_questions,
        policy_version=policy_version,
        trace_id=f"trace-{case.conversation_id}"[:64],
    )


def build_transfer(
    *,
    reason: TransferReason,
    customer: CustomerRecord,
    variant: LanguageVariant,
    claim_type: ClaimType | None,
    charges: tuple[ChargeDetail, ...],
    declared: DeclaredFacts,
    actions: tuple[Action, ...],
    pending_action: str | None,
    case_id: str | None,
    risk_signals: tuple[str, ...],
    fraud_alert: bool,
    rules_applied: tuple[str, ...],
    queue: Queue,
    policy_version: str,
    conversation_id: str,
    created_at: datetime,
) -> Transfer:
    """What is known when a conversation goes to a person without a case handoff, so nobody asks it again."""
    language = Language.PT if variant is LanguageVariant.PT else Language.ES
    summary = reason.value.replace("_", " ")
    if claim_type and claim_type.value != reason.value:
        summary += f": {claim_type.value.replace('_', ' ')}"
    summary += f", {len(charges)} charge(s) known"
    if pending_action:
        summary += f", {pending_action.replace('_', ' ')} pending and not run"
    open_questions = OPEN_QUESTIONS[reason]
    if reason is TransferReason.SCAM_TRANSFER:
        # POL-10: the key questions the customer did not answer stay open for the analyst.
        open_questions += (("When was the transfer made?",) if not declared.date_text else ()) + (
            ("How did the third party contact the customer?",) if not declared.contacted_by else ()
        )
    if "card_not_in_possession" in risk_signals:
        open_questions += (CARD_LAST_SEEN,)
    return Transfer(
        transfer_id=PENDING_TRANSFER_ID,
        created_at=created_at,
        reason=reason,
        summary=summary,
        language=language,
        variant=variant,
        requires_pt_analyst=language is Language.PT,
        account_country=customer.country,
        segment=Segment(customer.segment),
        claim_type=claim_type,
        charges=charges,
        declared_by_customer=declared,
        actions=actions,
        pending_action_not_run=pending_action,
        case_id=case_id,
        risk_signals=risk_signals,
        fraud_alert=fraud_alert,
        rules_applied=rules_applied,
        suggested_queue=queue,
        open_questions=open_questions,
        policy_version=policy_version,
        trace_id=f"trace-{conversation_id}"[:64],
    )


def _legal_clock(legal: LegalAssessment) -> LegalClock:
    evaluations = []
    for rule_id in legal.rules:
        dues = [due for due in legal.dues if due.rule_id == rule_id]
        dated = next((due for due in dues if due.due), None)
        evaluations.append(
            RuleEvaluation(
                id=rule_id,
                result=RuleResult.APPLIES,
                status=dated.status if dated else None,
                in_force_from=dated.in_force_from if dated else None,
                detail=None if dated else UNVERIFIED,
            )
        )
    obligations = tuple(
        Obligation(party=due.party, what=due.what, due=due.due, unit=due.unit)
        for due in legal.dues
        if due.due is not None or not legal.deadline_verified
    )
    return LegalClock(
        route=legal.route,
        rules_evaluated=tuple(evaluations),
        deadline_verified=legal.deadline_verified,
        obligations=obligations,
        venues=legal.venues,
    )
