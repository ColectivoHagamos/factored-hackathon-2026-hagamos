"""Contract tests for the handoff and the legal rule models."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from vera.contracts.handoff import GoodwillCandidate, GoodwillCriterion, Handoff, NetworkClock
from vera.contracts.legal import LegalRule

EXAMPLE = json.loads((Path(__file__).parent / "examples" / "handoff.json").read_text(encoding="utf-8"))
TEXT = "Test text used only to validate the contract."


def handoff_with(path: str, value) -> dict:
    data = copy.deepcopy(EXAMPLE)
    *parents, leaf = path.split(".")
    node = data
    for key in parents:
        node = node[int(key)] if key.isdigit() else node[key]
    node[int(leaf) if leaf.isdigit() else leaf] = value
    return data


def rule(**fields) -> dict:
    base = {
        "id": "CO-R15",
        "country": "CO",
        "route": "CO-bank-complaint",
        "literal_text": TEXT,
        "text_sha256": hashlib.sha256(TEXT.encode("utf-8")).hexdigest(),
        "source": {"title": "Law 1755 of 2015, articles 14 and 32", "url": "https://www.example.org/law-1755"},
        "effective_from": "2015-06-30",
        "level": "N1",
        "executable": True,
        "layer": "law",
        "party": "bank",
        "term_value": 15,
        "term_unit": "calendar_days",
    }
    return base | fields


class TestHandoff:
    def test_design_example_is_valid_and_round_trips(self):
        handoff = Handoff.model_validate(EXAMPLE)
        assert Handoff.model_validate_json(handoff.model_dump_json()) == handoff
        assert handoff.legal_clock.obligations[0].due.isoformat() == "2026-07-03"

    def test_raw_transcript_is_rejected(self):
        with pytest.raises(ValidationError):
            Handoff.model_validate(EXAMPLE | {"transcript": "full conversation"})

    @pytest.mark.parametrize(
        ("path", "value"),
        [
            ("requires_pt_analyst", False),
            ("variant", "es-CO"),
            ("legal_clock.deadline_verified", False),
            ("legal_clock.rules_evaluated.1.status", "early_adopted"),
            ("sweep.not_recognized", 5),
            ("actions.0.action", "refund"),
            ("network_clock.layer", "law"),
            ("response_level", 4),
            ("suggested_queue", "Fraud · Portuguese-speaking analyst"),
            ("verified_facts.charges", []),
            ("verified_facts.total_exposure.0.amount", "100000"),
        ],
    )
    def test_invalid_handoffs_are_rejected(self, path: str, value):
        with pytest.raises(ValidationError):
            Handoff.model_validate(handoff_with(path, value))

    def test_early_adopted_rule_states_its_legal_date(self):
        data = handoff_with("legal_clock.rules_evaluated.1.status", "early_adopted")
        data["legal_clock"]["rules_evaluated"][1]["in_force_from"] = "2026-11-19"
        assert Handoff.model_validate(data).legal_clock.rules_evaluated[1].in_force_from.month == 11

    def test_unverified_route_is_passed_on_without_a_date(self):
        data = handoff_with("legal_clock.deadline_verified", False)
        data["legal_clock"]["obligations"][0]["due"] = None
        assert Handoff.model_validate(data).legal_clock.obligations[0].due is None

    def test_goodwill_candidate_requires_the_three_criteria(self):
        criteria = list(GoodwillCriterion)
        with pytest.raises(ValidationError):
            GoodwillCandidate(flagged=True, criteria=criteria[:2], reason="first dispute, low amount")
        flagged = GoodwillCandidate(flagged=True, criteria=criteria, reason="bank charge of USD 12")
        assert flagged.flagged

    def test_network_clock_is_always_contractual(self):
        clock = NetworkClock.model_validate(EXAMPLE["network_clock"])
        assert clock.layer == "network"


class TestLegalRule:
    def test_n1_law_rule_is_executable(self):
        assert LegalRule(**rule()).executable

    @pytest.mark.parametrize(
        "fields",
        [
            {"level": "N2"},
            {"layer": "network"},
            {"term_unit": None},
            {"party": None},
            {"literal_text": TEXT + " Edited."},
            {"effective_to": "2014-01-01"},
            {"id": "CO-15"},
            {"source": {"title": "Law", "url": "not a url"}},
        ],
    )
    def test_invalid_rules_are_rejected(self, fields: dict):
        with pytest.raises(ValidationError):
            LegalRule(**rule(**fields))

    def test_n2_reference_is_informed_without_being_executable(self):
        reference = LegalRule(**rule(id="MX-R11", country="MX", route="MX-une", level="N2", executable=False))
        assert not reference.executable

    def test_immediate_obligation_needs_no_value(self):
        immediate = LegalRule(
            **rule(id="AR-R01", country="AR", route="AR-claim", term_value=None, term_unit="immediate")
        )
        assert immediate.term_value is None
