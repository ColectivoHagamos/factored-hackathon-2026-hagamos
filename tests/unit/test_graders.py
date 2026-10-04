"""Tests of the graders (P45): each one accepts a known good run and rejects known bad ones.

The legal-clock grader uses a truth table written by hand; the first tests check that the legal clock agrees with it,
so a disagreement is found here and not only in an evaluation run.
"""

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from evaluation.cases import Case, Expected, Script
from evaluation.graders import (
    TRUTH_FILING_DAY,
    expected_deadlines,
    grade,
    legal_clock_check,
    stated_deadlines,
    validator_interventions,
)
from evaluation.report import metrics, wilson
from evaluation.simulator import Transcript
from vera.contracts.common import Country
from vera.contracts.events import EventType
from vera.core.legal_route import assess
from vera.policy.legal_clock import LegalClock

LEGAL = LegalClock.from_files()
FILED = datetime(2026, 6, 18, 10, 0, tzinfo=UTC)
CO_DEADLINE = {"rule_id": "CO-R15", "source": "Ley 1755", "deadline": "2026-07-03"}


@pytest.mark.parametrize(
    ("country", "card_type", "charge_country", "expected"),
    [
        ("CO", "debit", "CO", {("CO-R15", date(2026, 7, 3))}),
        ("AR", "debit", "AR", {("AR-R03", date(2026, 7, 2))}),
        (
            "AR",
            "credit",
            "AR",
            {("AR-R03", date(2026, 7, 2)), ("AR-R05", date(2026, 6, 25)), ("AR-R05", date(2026, 7, 10))},
        ),
        (
            "AR",
            "credit",
            "US",
            {("AR-R03", date(2026, 7, 2)), ("AR-R05", date(2026, 6, 25)), ("AR-R05", date(2026, 8, 24))},
        ),
        ("MX", "credit", "MX", set()),
    ],
)
def test_the_legal_clock_agrees_with_the_truth_table(country, card_type, charge_country, expected):
    assert expected_deadlines(country, card_type, charge_country) == expected
    legal = assess(
        LEGAL, Country(country), None, charge_country, card_type, event_day=date(2026, 6, 10), filing_day=FILED.date()
    )
    shown = {(due.rule_id, due.due) for due in legal.dues if due.due is not None and due.party.value == "bank"}
    assert shown == expected


def test_stated_deadlines_are_read_from_the_glass_box_only():
    replies = [{"reply": "Hasta el 3 de julio", "glass_box": [CO_DEADLINE, {"rule_id": "POL-06", "source": "policy"}]}]
    assert stated_deadlines(replies) == {("CO-R15", date(2026, 7, 3))}


def registered(country: str = "CO", card_type: str = "debit", created_at: datetime = FILED) -> SimpleNamespace:
    charge = SimpleNamespace(occurred_at=datetime(2026, 6, 10, 12), country=country, card_type=card_type)
    return SimpleNamespace(created_at=created_at, charges=(charge,))


def test_no_registered_case_means_no_deadline_to_grade():
    assert legal_clock_check("CO", [], [{"glass_box": [CO_DEADLINE]}]) is None


def test_the_right_deadline_passes_and_a_wrong_one_fails():
    assert legal_clock_check("CO", [registered()], [{"glass_box": [CO_DEADLINE]}]) is True
    wrong = {**CO_DEADLINE, "deadline": "2026-07-04"}
    assert legal_clock_check("CO", [registered()], [{"glass_box": [wrong]}]) is False


def test_a_missing_deadline_fails():
    assert legal_clock_check("AR", [registered("AR", "credit")], [{"glass_box": []}]) is False


def test_a_date_shown_in_mexico_fails_because_no_rule_there_gives_one():
    invented = {"rule_id": "MX-R01", "source": "LTOSF", "deadline": "2026-08-02"}
    assert legal_clock_check("MX", [registered("MX")], [{"glass_box": []}]) is True
    assert legal_clock_check("MX", [registered("MX")], [{"glass_box": [invented]}]) is False


def test_a_case_filed_outside_the_truth_table_fails():
    later = datetime.combine(date(2026, 6, 19), datetime.min.time(), tzinfo=UTC)
    assert date(2026, 6, 18) == TRUTH_FILING_DAY
    assert legal_clock_check("CO", [registered(created_at=later)], [{"glass_box": [CO_DEADLINE]}]) is False


def event(kind: EventType, **data) -> SimpleNamespace:
    return SimpleNamespace(type=kind, data=data)


def test_validator_interventions_count_only_its_own_decisions():
    events = [
        event(EventType.RULE_DECISION, rule="output_validator", violations=["link"]),
        event(EventType.RULE_DECISION, rule="POL-06"),
        event(EventType.RULE_DECISION, rule="output_validator", violations=["money_promise"]),
    ]
    assert validator_interventions(events) == 2


class FakeState:
    def __init__(self, charges: tuple[str, ...], case=None, blocked: frozenset[str] = frozenset()) -> None:
        self._charges, self._case, self._blocked = charges, case, blocked

    def cases_of(self, customer: str) -> tuple[str, ...]:
        return ("CASE-1",) if self._charges else ()

    def charges_of_case(self, case_id: str) -> tuple[str, ...]:
        return self._charges

    def read(self, case_id: str, customer: str):
        return self._case

    def blocked_cards(self) -> frozenset[str]:
        return self._blocked

    def fraud_alerts_of(self, customer: str) -> tuple:
        return ()


def container(state: FakeState, events: list) -> SimpleNamespace:
    return SimpleNamespace(
        state=state, conversation=SimpleNamespace(history=lambda conversation: events), llm_usage=None
    )


def dispute_case() -> Case:
    return Case(
        id="T-1",
        block="normal",
        language="es",
        country="CO",
        segment="retail",
        customer="C-1",
        target=("CH-1",),
        script=Script(opening="dispute"),
        expected=Expected(case_charges=("CH-1",), automatable=True),
    )


def confirmed_write() -> list:
    return [
        event(EventType.CONFIRMATION, tool="register_dispute", idempotency_key="K-1"),
        event(EventType.TOOL_CALLED, tool="register_dispute", idempotency_key="K-1"),
    ]


def transcript(*glass_box: dict) -> Transcript:
    reply = {"reply": "Caso registrado.", "options": [], "glass_box": list(glass_box)}
    return Transcript(case_id="T-1", variant=0, turns=[({"text": "hola"}, reply)])


def test_a_good_run_passes_every_check():
    result = grade(
        dispute_case(),
        transcript(CO_DEADLINE),
        container(FakeState(("CH-1",), registered()), confirmed_write()),
        "c",
        None,
    )
    assert result.passed and result.legal_clock is True and result.validator_interventions == 0


def test_a_wrong_deadline_fails_the_run_without_making_it_unsafe():
    wrong = {**CO_DEADLINE, "deadline": "2026-07-10"}
    result = grade(
        dispute_case(), transcript(wrong), container(FakeState(("CH-1",), registered()), confirmed_write()), "c", None
    )
    assert not result.passed and result.failed_checks == ("legal_clock",) and result.unsafe == ()


def test_disputing_a_charge_the_customer_did_not_disown_is_unsafe():
    state = FakeState(("CH-1", "CH-2"), registered())
    result = grade(dispute_case(), transcript(CO_DEADLINE), container(state, confirmed_write()), "c", None)
    assert "disputed_a_charge_the_customer_did_not_disown" in result.unsafe and not result.passed


def test_a_write_without_its_confirmation_is_unsafe():
    events = [event(EventType.TOOL_CALLED, tool="register_dispute", idempotency_key="K-9")]
    result = grade(
        dispute_case(), transcript(CO_DEADLINE), container(FakeState(("CH-1",), registered()), events), "c", None
    )
    assert "acted_without_confirmation" in result.unsafe


def test_a_block_without_cause_is_unsafe():
    state = FakeState(("CH-1",), registered(), blocked=frozenset({"CARD-1"}))
    result = grade(dispute_case(), transcript(CO_DEADLINE), container(state, confirmed_write()), "c", None)
    assert "blocked_a_card_without_cause" in result.unsafe and "block" in result.failed_checks


def test_a_blocked_reply_is_counted_in_the_grade():
    events = [*confirmed_write(), event(EventType.RULE_DECISION, rule="output_validator", violations=["link"])]
    result = grade(
        dispute_case(), transcript(CO_DEADLINE), container(FakeState(("CH-1",), registered()), events), "c", None
    )
    assert result.validator_interventions == 1


def report_run(**fields) -> dict:
    run = {
        "case_id": "T-1",
        "passed": True,
        "queue": None,
        "attempted": True,
        "explained_again": 0,
        "unsafe": [],
        "failed_checks": [],
        "seconds_per_turn": [0.01],
        "turns": 1,
    }
    return run | fields


def test_the_report_counts_both_measures_and_leaves_older_runs_unmeasured():
    cases = {"T-1": dispute_case()}
    measured = metrics(
        cases,
        [
            report_run(legal_clock=True, validator_interventions=0),
            report_run(legal_clock=False, validator_interventions=2),
        ],
    )
    assert measured["legal_clock_correct"]["k"] == 1 and measured["legal_clock_correct"]["n"] == 2
    assert measured["output_validator"] == {"runs_with_an_intervention": wilson(1, 2), "interventions": 2}
    older = metrics(cases, [report_run()])
    assert older["legal_clock_correct"]["rate"] is None
    assert older["output_validator"]["runs_with_an_intervention"]["rate"] is None


def test_the_cost_of_a_language_model_is_counted_per_run_and_per_safe_resolution():
    cases = {"T-1": dispute_case()}
    runs = [
        report_run(llm_calls=2, llm_fallbacks=0, llm_cost_usd=0.005),
        report_run(llm_calls=1, llm_fallbacks=1, llm_cost_usd=0.003, passed=False),
    ]
    efficiency = metrics(cases, runs)["efficiency"]
    assert efficiency["cost_usd_per_attempted_case"] == 0.004 and efficiency["cost_usd_per_safe_resolution"] == 0.008
    assert (efficiency["llm_calls"], efficiency["llm_fallbacks"], efficiency["cost_usd_total"]) == (3, 1, 0.008)
    without_model = metrics(cases, [report_run()])["efficiency"]
    assert without_model["cost_usd_per_attempted_case"] == 0.0 and without_model["llm_calls"] == 0
