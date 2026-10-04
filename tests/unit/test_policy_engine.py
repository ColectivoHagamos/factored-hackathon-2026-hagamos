"""Tests of the policy engine (P12): one positive and one negative example per rule, plus the invariants."""

from decimal import Decimal

import pytest

from vera.contracts.charges import FraudScoreBand
from vera.contracts.common import Money
from vera.contracts.handoff import Queue
from vera.policy.engine import PREDICATES, Facts, Outcome, PolicyEngine, Signal, exposure_usd
from vera.policy.model import load_policy

POLICY = load_policy()
ENGINE = PolicyEngine(POLICY)
BASE = Facts(account_country="CO")


def replace(facts: Facts, **updates) -> Facts:
    """Validated copy: strings are converted to their enums, as at the boundary."""
    return Facts.model_validate(facts.model_dump() | updates)


# rule: (facts that trigger it, facts that are almost the same and do not, expected outcome)
CASES = {
    "POL-01": ({"human_requested": True}, {"human_requested": False}, Outcome.OFFER_BEFORE_TRANSFER),
    "POL-02": ({"coercion": True}, {"coercion": False}, Outcome.HANDOFF),
    "POL-03": ({"instruction_in_message": True}, {"instruction_in_message": False}, Outcome.SECURITY_EVENT),
    "POL-04": ({"charge_status": "pending"}, {"charge_status": "approved"}, Outcome.EXPLAIN_STATUS),
    "POL-05": ({"candidates_found": 2}, {"candidates_found": 1}, Outcome.CUSTOMER_CHOOSES),
    "POL-06": (
        {"signals": frozenset({Signal.CARD_NOT_IN_POSSESSION})},
        {"signals": frozenset({Signal.NEW_MERCHANT})},
        Outcome.OFFER_BLOCK,
    ),
    "POL-07": ({"total_exposure_usd": Decimal("400")}, {"total_exposure_usd": Decimal("399.99")}, Outcome.HANDOFF),
    "POL-08": ({"disputes_in_window": 2}, {"disputes_in_window": 1}, Outcome.HANDOFF),
    "POL-09": ({"regulator_mentioned": True}, {"regulator_mentioned": False}, Outcome.INFORM_VENUE),
    "POL-10": ({"claim_type": "scam_transfer"}, {"claim_type": "unrecognized_charge"}, Outcome.KEY_QUESTIONS),
    "POL-11": ({"claim_type": "improper_charge"}, {"claim_type": "unrecognized_charge"}, Outcome.IDENTIFY_CHARGE),
    "POL-12": ({"eligible_route": False}, {"eligible_route": True}, Outcome.NOT_ELIGIBLE),
    "POL-13": ({"read_back_mismatch": True}, {"read_back_mismatch": False}, Outcome.HANDOFF),
    "POL-14": ({"interpreter_confidence": 0.59}, {"interpreter_confidence": 0.6}, Outcome.ASK_INSTEAD_OF_ACT),
    "POL-15": ({"pix_mentioned": True}, {"pix_mentioned": False}, Outcome.OUT_OF_SCOPE),
    "POL-16": (
        {"signals": frozenset({Signal.FRAUD_SCORE_ABOVE_THRESHOLD})},
        {"signals": frozenset({Signal.NEW_MERCHANT})},
        Outcome.FRAUD_ALERT,
    ),
    "POL-17": (
        {"already_escalated": True, "first_dispute_in_goodwill_window": True, "bank_charge": True},
        {"already_escalated": True, "first_dispute_in_goodwill_window": False, "bank_charge": True},
        Outcome.GOODWILL_CANDIDATE,
    ),
}


def decision(evaluation, rule_id):
    return next((d for d in evaluation.decisions if d.rule == rule_id), None)


def test_every_rule_of_the_policy_has_a_predicate_and_two_tests():
    assert {rule.id for rule in POLICY.rules} == set(PREDICATES) == set(CASES)


@pytest.mark.parametrize("rule_id", sorted(CASES))
def test_rule_applies_when_its_condition_holds(rule_id: str):
    positive, _, outcome = CASES[rule_id]
    found = decision(ENGINE.evaluate(replace(BASE, **positive)), rule_id)
    assert found is not None and found.outcome is outcome
    assert found.version == POLICY.version == "1.5"
    assert found.as_event_data()["rule"] == rule_id


@pytest.mark.parametrize("rule_id", sorted(CASES))
def test_rule_does_not_apply_when_its_condition_fails(rule_id: str):
    _, negative, _ = CASES[rule_id]
    assert decision(ENGINE.evaluate(replace(BASE, **negative)), rule_id) is None


def test_nothing_applies_to_a_plain_turn():
    evaluation = ENGINE.evaluate(BASE)
    assert evaluation.decisions == () and not evaluation.escalate and evaluation.queue is None


def test_pol01_offers_once_and_then_transfers():
    asked = ENGINE.evaluate(replace(BASE, human_requested=True))
    assert asked.outcomes == {Outcome.OFFER_BEFORE_TRANSFER} and not asked.escalate
    offers = POLICY.parameters.offers_before_transfer
    insisted = ENGINE.evaluate(replace(BASE, human_requested=True, person_offers_made=offers))
    assert offers == 1 and insisted.outcomes == {Outcome.HANDOFF} and insisted.escalate


def test_pol01_without_offers_transfers_at_once():
    parameters = POLICY.parameters.model_copy(update={"offers_before_transfer": 0})
    engine = PolicyEngine(POLICY.model_copy(update={"parameters": parameters}))
    assert engine.evaluate(replace(BASE, human_requested=True)).outcomes == {Outcome.HANDOFF}


def test_coercion_never_waits_for_an_offer():
    evaluation = ENGINE.evaluate(replace(BASE, human_requested=True, coercion=True))
    assert Outcome.HANDOFF in evaluation.outcomes and evaluation.escalate and evaluation.queue is Queue.FRAUD


def test_escalation_floor_is_never_lowered():
    evaluation = ENGINE.evaluate(replace(BASE, already_escalated=True, eligible_route=False))
    assert Outcome.NOT_ELIGIBLE in evaluation.outcomes
    assert evaluation.escalate


def test_not_eligible_dispute_is_still_contained_and_alerted():
    signals = frozenset({Signal.CARD_NOT_IN_POSSESSION})
    evaluation = ENGINE.evaluate(replace(BASE, eligible_route=False, signals=signals))
    assert {Outcome.NOT_ELIGIBLE, Outcome.FRAUD_ALERT} <= evaluation.outcomes
    # Containment still happens: POL-06 escalates to Fraud even though the dispute itself is not eligible.
    assert evaluation.queue is Queue.FRAUD


def test_fraud_score_alone_alerts_but_never_contains():
    evaluation = ENGINE.evaluate(replace(BASE, signals=frozenset({Signal.FRAUD_SCORE_ABOVE_THRESHOLD})))
    assert evaluation.outcomes == {Outcome.FRAUD_ALERT}
    assert not evaluation.escalate


def test_argentina_offers_the_block_only_at_the_customers_request():
    signals = frozenset({Signal.MULTIPLE_UNRECOGNIZED})
    assert Outcome.BLOCK_ON_CUSTOMER_REQUEST in ENGINE.evaluate(Facts(account_country="AR", signals=signals)).outcomes
    assert Outcome.OFFER_BLOCK in ENGINE.evaluate(Facts(account_country="MX", signals=signals)).outcomes


def test_valid_authentication_never_changes_a_decision():
    rich = replace(
        BASE,
        claim_type="unrecognized_charge",
        signals=frozenset({Signal.CARD_NOT_IN_POSSESSION, Signal.FRAUD_SCORE_ABOVE_THRESHOLD}),
        total_exposure_usd=Decimal("450"),
        disputes_in_window=2,
    )
    assert ENGINE.evaluate(rich) == ENGINE.evaluate(replace(rich, valid_authentication=True))


def test_fraud_queue_wins_over_complaints():
    facts = replace(BASE, signals=frozenset({Signal.CARD_NOT_IN_POSSESSION}), total_exposure_usd=Decimal("500"))
    assert ENGINE.evaluate(facts).queue is Queue.FRAUD
    assert ENGINE.evaluate(replace(BASE, total_exposure_usd=Decimal("500"))).queue is Queue.COMPLAINTS


def test_search_without_results_asks_until_the_attempts_run_out():
    asking = ENGINE.evaluate(replace(BASE, candidates_found=0, question_attempts=2))
    assert asking.outcomes == {Outcome.ASK_DETAIL} and not asking.escalate
    exhausted = ENGINE.evaluate(replace(BASE, candidates_found=0, question_attempts=3))
    assert exhausted.outcomes == {Outcome.HANDOFF} and exhausted.escalate


def test_goodwill_requires_a_case_for_the_analyst_and_a_low_amount():
    criteria = {"first_dispute_in_goodwill_window": True, "customer_recognized_charge": True}
    assert decision(ENGINE.evaluate(replace(BASE, **criteria)), "POL-17") is None
    over_limit = replace(BASE, already_escalated=True, total_exposure_usd=Decimal("100.01"), **criteria)
    assert decision(ENGINE.evaluate(over_limit), "POL-17") is None


def test_exposure_in_usd_uses_the_fixed_dataset_rates():
    rates = POLICY.parameters.usd_rates
    assert exposure_usd([Money(amount=Decimal("185000"), currency="COP")], rates) == Decimal("46.25")
    mixed = [Money(amount=Decimal("1600000"), currency="COP"), Money(amount=Decimal("35000"), currency="ARS")]
    assert exposure_usd(mixed, rates) == Decimal("500.00")


def test_score_threshold_matches_the_band_published_by_the_contracts():
    assert POLICY.parameters.fraud_score_threshold == 30
    assert {band.value for band in FraudScoreBand} == {"<=30", ">30", "none"}


def test_engine_refuses_a_policy_without_predicates():
    with pytest.raises(ValueError, match="differ"):
        PolicyEngine(POLICY.model_copy(update={"rules": POLICY.rules[:-1]}))


def test_facts_have_no_field_that_decides_on_money():
    assert not any("refund" in name or "reimburse" in name for name in Facts.model_fields)
