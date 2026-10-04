"""Policy engine: evaluates the facts of a turn and returns decisions that cite the rule id and version.

Conditions live here, in code; the policy YAML carries the version, the parameters and the text of each rule.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from pydantic import JsonValue

from vera.contracts.charges import ChargeStatus
from vera.contracts.common import Contract, Country, Currency, Money
from vera.contracts.handoff import Queue
from vera.contracts.interpretation import ClaimType
from vera.policy.model import Parameters, Policy


class Signal(StrEnum):
    """Alert signals of policy section 7.1."""

    CARD_NOT_IN_POSSESSION = "card_not_in_possession"
    CUSTOMER_DID_NOT_TRAVEL = "customer_did_not_travel"
    MULTIPLE_UNRECOGNIZED = "multiple_unrecognized_charges"
    FRAUD_SCORE_ABOVE_THRESHOLD = "fraud_score_above_threshold"
    FOREIGN_CHARGE_CUSTOMER_NOT_THERE = "foreign_charge_customer_not_there"
    UNRECOGNIZED_NON_APPROVED = "unrecognized_non_approved_charge"
    NEW_MERCHANT = "new_merchant"


# A new merchant adds to the picture but never decides.
STRONG_SIGNALS = frozenset(Signal) - {Signal.NEW_MERCHANT}
NOT_DISPUTABLE = frozenset({ChargeStatus.PENDING, ChargeStatus.DECLINED, ChargeStatus.REVERSED})


class Outcome(StrEnum):
    HANDOFF = "handoff"
    SECURITY_EVENT = "security_event"
    EXPLAIN_STATUS = "explain_status"
    ASK_DETAIL = "ask_detail"
    CUSTOMER_CHOOSES = "customer_chooses"
    OFFER_BLOCK = "offer_block"
    BLOCK_ON_CUSTOMER_REQUEST = "block_on_customer_request"
    INFORM_VENUE = "inform_venue"
    KEY_QUESTIONS = "key_questions"
    IDENTIFY_CHARGE = "identify_charge"
    NOT_ELIGIBLE = "not_eligible"
    ASK_INSTEAD_OF_ACT = "ask_instead_of_act"
    OUT_OF_SCOPE = "out_of_scope"
    FRAUD_ALERT = "fraud_alert"
    GOODWILL_CANDIDATE = "goodwill_candidate"


class Facts(Contract):
    """What is known in a turn: stated by the customer, interpreted, or read from tools."""

    account_country: Country
    claim_type: ClaimType | None = None
    interpreter_confidence: float | None = None
    human_requested: bool = False
    coercion: bool = False
    instruction_in_message: bool = False
    foreign_charge_requested: bool = False
    regulator_mentioned: bool = False
    pix_mentioned: bool = False
    candidates_found: int | None = None
    question_attempts: int = 0
    charge_status: ChargeStatus | None = None
    signals: frozenset[Signal] = frozenset()
    total_exposure_usd: Decimal = Decimal(0)
    disputes_in_window: int = 0
    tool_failed: bool = False
    read_back_mismatch: bool = False
    # Result of the legal engine; None while no route has been evaluated.
    eligible_route: bool | None = None
    first_dispute_in_goodwill_window: bool = False
    customer_recognized_charge: bool = False
    bank_charge: bool = False
    already_escalated: bool = False
    # PROH-04: kept only to prove that valid authentication never changes a decision.
    valid_authentication: bool = False


@dataclass(frozen=True)
class Effect:
    outcome: Outcome
    escalate: bool = False
    queue: Queue | None = None


@dataclass(frozen=True)
class RuleDecision:
    rule: str
    version: str
    outcome: Outcome
    escalate: bool
    queue: Queue | None

    def as_event_data(self) -> dict[str, JsonValue]:
        """Payload of the rule_decision event."""
        return {
            "rule": self.rule,
            "version": self.version,
            "outcome": self.outcome.value,
            "escalate": self.escalate,
            "queue": self.queue.value if self.queue else None,
        }


@dataclass(frozen=True)
class Evaluation:
    decisions: tuple[RuleDecision, ...]
    escalate: bool
    queue: Queue | None

    @property
    def outcomes(self) -> frozenset[Outcome]:
        return frozenset(decision.outcome for decision in self.decisions)

    @property
    def rules(self) -> tuple[str, ...]:
        return tuple(decision.rule for decision in self.decisions)


Predicate = Callable[[Facts, Parameters, bool], Effect | None]


def _human_requested(f: Facts, p: Parameters, escalating: bool) -> Effect | None:
    return Effect(Outcome.HANDOFF, escalate=True) if f.human_requested else None


def _coercion(f: Facts, p: Parameters, escalating: bool) -> Effect | None:
    return Effect(Outcome.HANDOFF, escalate=True, queue=Queue.FRAUD) if f.coercion else None


def _instruction_or_foreign_charge(f: Facts, p: Parameters, escalating: bool) -> Effect | None:
    return Effect(Outcome.SECURITY_EVENT) if f.instruction_in_message or f.foreign_charge_requested else None


def _not_disputable_status(f: Facts, p: Parameters, escalating: bool) -> Effect | None:
    return Effect(Outcome.EXPLAIN_STATUS) if f.charge_status in NOT_DISPUTABLE else None


def _ambiguous_search(f: Facts, p: Parameters, escalating: bool) -> Effect | None:
    if f.candidates_found == 0:
        if f.question_attempts >= p.max_question_attempts:
            return Effect(Outcome.HANDOFF, escalate=True)
        return Effect(Outcome.ASK_DETAIL)
    if f.candidates_found is not None and f.candidates_found >= 2:
        return Effect(Outcome.CUSTOMER_CHOOSES)
    return None


def _alert_signals(f: Facts, p: Parameters, escalating: bool) -> Effect | None:
    # PROH-02: the fraud score corroborates other signals but never triggers containment by itself.
    if not (f.signals & STRONG_SIGNALS) - {Signal.FRAUD_SCORE_ABOVE_THRESHOLD}:
        return None
    # Section 7.3 and AR-R06: in Argentina the block is offered only for security, at the customer's request.
    outcome = Outcome.BLOCK_ON_CUSTOMER_REQUEST if f.account_country is Country.AR else Outcome.OFFER_BLOCK
    return Effect(outcome, escalate=True, queue=Queue.FRAUD)


def _high_exposure(f: Facts, p: Parameters, escalating: bool) -> Effect | None:
    if f.total_exposure_usd >= p.exposure_threshold_usd:
        return Effect(Outcome.HANDOFF, escalate=True, queue=Queue.COMPLAINTS)
    return None


def _repeat_disputes(f: Facts, p: Parameters, escalating: bool) -> Effect | None:
    if f.disputes_in_window >= p.repeat_disputes:
        return Effect(Outcome.HANDOFF, escalate=True, queue=Queue.COMPLAINTS)
    return None


def _regulator(f: Facts, p: Parameters, escalating: bool) -> Effect | None:
    return Effect(Outcome.INFORM_VENUE, escalate=True, queue=Queue.COMPLAINTS) if f.regulator_mentioned else None


def _scam_transfer(f: Facts, p: Parameters, escalating: bool) -> Effect | None:
    if f.claim_type is ClaimType.SCAM_TRANSFER:
        return Effect(Outcome.KEY_QUESTIONS, escalate=True, queue=Queue.FRAUD)
    return None


def _improper_charge(f: Facts, p: Parameters, escalating: bool) -> Effect | None:
    if f.claim_type is ClaimType.IMPROPER_CHARGE:
        return Effect(Outcome.IDENTIFY_CHARGE, escalate=True, queue=Queue.COMPLAINTS)
    return None


def _no_eligible_route(f: Facts, p: Parameters, escalating: bool) -> Effect | None:
    # Not eligible is not escalated by this rule; the escalation floor keeps any earlier handoff.
    return Effect(Outcome.NOT_ELIGIBLE) if f.eligible_route is False else None


def _tool_failure(f: Facts, p: Parameters, escalating: bool) -> Effect | None:
    if f.tool_failed or f.read_back_mismatch:
        return Effect(Outcome.HANDOFF, escalate=True, queue=Queue.COMPLAINTS)
    return None


def _low_confidence(f: Facts, p: Parameters, escalating: bool) -> Effect | None:
    if f.interpreter_confidence is not None and f.interpreter_confidence < p.interpreter_min_confidence:
        return Effect(Outcome.ASK_INSTEAD_OF_ACT)
    return None


def _pix(f: Facts, p: Parameters, escalating: bool) -> Effect | None:
    return Effect(Outcome.OUT_OF_SCOPE) if f.pix_mentioned else None


def _fraud_alert(f: Facts, p: Parameters, escalating: bool) -> Effect | None:
    return Effect(Outcome.FRAUD_ALERT) if f.signals & STRONG_SIGNALS else None


def _goodwill_candidate(f: Facts, p: Parameters, escalating: bool) -> Effect | None:
    meets_criteria = (
        f.first_dispute_in_goodwill_window
        and f.total_exposure_usd <= p.goodwill_max_usd
        and (f.customer_recognized_charge or f.bank_charge)
    )
    return Effect(Outcome.GOODWILL_CANDIDATE) if escalating and meets_criteria else None


# Evaluation order: a human first, then the rules in id order; the alert and the goodwill flag see everything else.
PREDICATES: dict[str, Predicate] = {
    "POL-01": _human_requested,
    "POL-02": _coercion,
    "POL-03": _instruction_or_foreign_charge,
    "POL-04": _not_disputable_status,
    "POL-05": _ambiguous_search,
    "POL-06": _alert_signals,
    "POL-07": _high_exposure,
    "POL-08": _repeat_disputes,
    "POL-09": _regulator,
    "POL-10": _scam_transfer,
    "POL-11": _improper_charge,
    "POL-12": _no_eligible_route,
    "POL-13": _tool_failure,
    "POL-14": _low_confidence,
    "POL-15": _pix,
    "POL-16": _fraud_alert,
    "POL-17": _goodwill_candidate,
}


class PolicyEngine:
    def __init__(self, policy: Policy) -> None:
        rule_ids = {rule.id for rule in policy.rules}
        if rule_ids != set(PREDICATES):
            raise ValueError(f"policy rules and engine predicates differ: {sorted(rule_ids ^ set(PREDICATES))}")
        self._policy = policy

    @property
    def version(self) -> str:
        return self._policy.version

    @property
    def parameters(self) -> Parameters:
        return self._policy.parameters

    def evaluate(self, facts: Facts) -> Evaluation:
        decisions: list[RuleDecision] = []
        escalating = facts.already_escalated
        for rule_id, predicate in PREDICATES.items():
            effect = predicate(facts, self._policy.parameters, escalating)
            if effect is None:
                continue
            decisions.append(RuleDecision(rule_id, self._policy.version, effect.outcome, effect.escalate, effect.queue))
            # Escalation floor: once a rule escalates, no later rule or model lowers it.
            escalating = escalating or effect.escalate
        return Evaluation(tuple(decisions), escalating, _queue(decisions))


def _queue(decisions: Sequence[RuleDecision]) -> Queue | None:
    """Queue proposed in this turn; None keeps the queue chosen when the case was first escalated."""
    escalating = [decision for decision in decisions if decision.escalate]
    if not escalating:
        return None
    return Queue.FRAUD if any(decision.queue is Queue.FRAUD for decision in escalating) else Queue.COMPLAINTS


def exposure_usd(total_exposure: Sequence[Money], rates: dict[Currency, Decimal]) -> Decimal:
    """Total exposure in USD with the fixed dataset rates, used only for thresholds."""
    total = sum((money.amount / rates[money.currency] for money in total_exposure), Decimal(0))
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
