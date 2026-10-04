"""Builder of the structured handoff for the analyst. Verified facts come only from tools; the transcript never goes."""

from datetime import datetime

from vera.contracts.cases import Case
from vera.contracts.charges import FraudScoreBand
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
    VerifiedFacts,
)
from vera.contracts.legal import Level
from vera.core.legal_route import LegalAssessment, network_code, network_due
from vera.ports.bank import CustomerRecord

UNVERIFIED = "literal text pending verification: informed without a date"


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
