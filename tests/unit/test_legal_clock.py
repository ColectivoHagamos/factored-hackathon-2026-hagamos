"""Tests of the legal clock (P14): business days per country and dates only from executable rules."""

import hashlib
from datetime import date

import pytest

from vera.contracts.legal import LegalRule
from vera.policy.legal_clock import LegalClock, load_calendars, load_rules, status_on

CLOCK = date(2026, 6, 18)
CALENDARS = load_calendars()
LEGAL = LegalClock.from_files()


@pytest.mark.parametrize(
    ("country", "days", "expected"),
    [
        ("CO", 5, date(2026, 6, 25)),
        ("CO", 15, date(2026, 7, 10)),
        ("AR", 10, date(2026, 7, 2)),
        ("MX", 2, date(2026, 6, 22)),
    ],
)
def test_business_days_match_the_design_examples(country: str, days: int, expected: date):
    assert CALENDARS[country].add_business_days(CLOCK, days) == expected


def test_weekends_and_holidays_are_not_business_days():
    co = CALENDARS["CO"]
    assert not co.is_business_day(date(2026, 6, 20))  # Saturday
    assert not co.is_business_day(date(2026, 6, 29))  # Saint Peter and Saint Paul
    assert co.is_business_day(date(2026, 6, 30))


def test_bank_complaint_in_colombia_is_due_in_15_calendar_days():
    (due,) = LEGAL.deadlines("CO-R15", event_day=date(2026, 6, 14), filing_day=CLOCK)
    assert (due.party, due.unit, due.due, due.status) == ("bank", "calendar_days", date(2026, 7, 3), "in_force_by_law")


def test_card_statement_challenge_in_argentina_chains_acknowledgment_and_answer():
    customer, acknowledgment, answer = LEGAL.deadlines("AR-R05", event_day=date(2026, 6, 10), filing_day=CLOCK)
    assert (customer.unit, customer.due) == ("business_days", CALENDARS["AR"].add_business_days(date(2026, 6, 10), 30))
    assert (acknowledgment.unit, acknowledgment.due) == ("calendar_days", date(2026, 6, 25))
    assert answer.due == date(2026, 7, 10)


def test_operations_abroad_replace_the_general_answer_term():
    dues = LEGAL.deadlines(
        "AR-R05", event_day=date(2026, 6, 10), filing_day=CLOCK, conditions=frozenset({"charge_abroad"})
    )
    assert [due.due for due in dues][2:] == [date(2026, 8, 24)]
    assert len(dues) == 3


def test_terms_that_start_later_have_no_date_yet():
    (due,) = LEGAL.deadlines("AR-R08", event_day=CLOCK, filing_day=CLOCK)
    assert due.due is None and "later event" in due.reason


@pytest.mark.parametrize("rule_id", ["MX-R01", "MX-R03", "AR-R01"])
def test_rules_without_verified_literal_text_never_give_a_date(rule_id: str):
    dues = LEGAL.deadlines(rule_id, event_day=CLOCK, filing_day=CLOCK)
    assert dues and all(due.due is None and "literal text" in due.reason for due in dues)


def test_every_executable_rule_carries_its_official_text_and_fingerprint():
    executable = [rule for rule in load_rules() if rule.executable]
    assert {rule.id for rule in executable} == {"CO-R15", "AR-R03", "AR-R05", "AR-R06", "AR-R07", "AR-R08"}
    for rule in executable:
        assert hashlib.sha256(rule.literal_text.encode("utf-8")).hexdigest() == rule.text_sha256


def rule(**fields) -> LegalRule:
    text = "Texto de prueba."
    base = {
        "id": "CO-R06",
        "country": "CO",
        "route": "CO-impersonation",
        "summary": "Test rule",
        "source": {"title": "Test", "provision": "art. 1", "url": "https://www.example.org/test"},
        "literal_text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "level": "N1",
        "executable": True,
        "layer": "law",
        "terms": [
            {
                "party": "bank",
                "what": "act",
                "value": 5,
                "unit": "business_days",
                "starts_at": "filing",
                "counts_from": "filing",
            }
        ],
    }
    return LegalRule.model_validate(base | fields)


def test_early_adopted_rule_gives_dates_and_states_when_it_becomes_law():
    early = rule(effective_from="2026-11-19", early_adoption=True)
    assert status_on(early, CLOCK) == "early_adopted"
    assert status_on(early, date(2026, 11, 19)) == "in_force_by_law"
    (due,) = LegalClock([early], CALENDARS).deadlines("CO-R06", event_day=CLOCK, filing_day=CLOCK)
    assert due.due == date(2026, 6, 25) and due.in_force_from == date(2026, 11, 19)


def test_a_rule_not_yet_in_force_and_not_adopted_gives_no_date():
    future = rule(effective_from="2026-11-19")
    (due,) = LegalClock([future], CALENDARS).deadlines("CO-R06", event_day=CLOCK, filing_day=CLOCK)
    assert due.due is None and due.status is None and "not in force" in due.reason
