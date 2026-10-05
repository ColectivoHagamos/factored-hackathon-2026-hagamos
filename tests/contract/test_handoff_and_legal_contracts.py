"""Contract tests for the handoff and the legal rule models."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from vera.adapters.sqlite_state import SqliteState
from vera.contracts.handoff import GoodwillCandidate, GoodwillCriterion, Handoff, NetworkClock, Transfer
from vera.contracts.legal import LegalRule

EXAMPLE = json.loads((Path(__file__).parent / "examples" / "handoff.json").read_text(encoding="utf-8"))
TRANSFER = json.loads((Path(__file__).parent / "examples" / "transfer.json").read_text(encoding="utf-8"))
TEXT = "Test text used only to validate the contract."


def handoff_with(path: str, value) -> dict:
    data = copy.deepcopy(EXAMPLE)
    *parents, leaf = path.split(".")
    node = data
    for key in parents:
        node = node[int(key)] if key.isdigit() else node[key]
    node[int(leaf) if leaf.isdigit() else leaf] = value
    return data


TERM = {"party": "bank", "what": "answer", "value": 15, "unit": "days", "starts_at": "receipt", "counts_from": "filing"}


def rule(**fields) -> dict:
    base = {
        "id": "CO-R15",
        "country": "CO",
        "route": "CO-bank-complaint",
        "summary": "Petitions are answered within 15 days",
        "literal_text": TEXT,
        "text_sha256": hashlib.sha256(TEXT.encode("utf-8")).hexdigest(),
        "source": {"title": "Ley 1755 de 2015", "provision": "arts. 14 and 32", "url": "https://www.example.org/law"},
        "effective_from": "2015-06-30",
        "level": "N1",
        "executable": True,
        "layer": "law",
        "terms": [TERM],
    }
    return base | fields


class TestHandoff:
    def test_a_handoff_stored_as_2_0_still_reads_and_lists_in_the_queue(self):
        # Handoffs written before 2.1 stay in a deployment's state; the analyst queue must keep reading them.
        stored = {key: value for key, value in EXAMPLE.items() if key != "rules_applied"} | {
            "schema_version": "handoff/2.0"
        }
        old = Handoff.model_validate(stored)
        assert old.schema_version == "handoff/2.0" and old.rules_applied == ()
        state = SqliteState()
        state.hand_off(old, old.suggested_queue)
        assert [item.case_id for item in state.queue()] == [old.case_id]

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
    def test_n1_law_rule_with_its_literal_text_is_executable(self):
        assert LegalRule(**rule()).executable

    @pytest.mark.parametrize(
        "fields",
        [
            {"level": "N2"},
            {"layer": "network"},
            {"literal_text": None, "text_sha256": None},
            {"literal_text": TEXT + " Edited."},
            {"text_sha256": None},
            {"effective_to": "2014-01-01"},
            {"early_adoption": True, "effective_from": None},
            {"id": "CO-15"},
            {"terms": [TERM | {"unit": "immediate"}]},
            {"terms": [TERM | {"follows": "missing"}]},
            {"source": {"title": "Law", "provision": "art. 1", "url": "not a url"}},
        ],
    )
    def test_invalid_rules_are_rejected(self, fields: dict):
        with pytest.raises(ValidationError):
            LegalRule(**rule(**fields))

    def test_rule_pending_its_literal_text_is_kept_but_not_executable(self):
        pending = LegalRule(
            **rule(
                id="MX-R01",
                country="MX",
                route="MX-clarification",
                literal_text=None,
                text_sha256=None,
                executable=False,
            )
        )
        assert not pending.executable and pending.literal_text is None

    def test_immediate_obligation_needs_no_value(self):
        immediate = TERM | {"unit": "immediate", "value": None}
        assert LegalRule(**rule(id="AR-R01", country="AR", route="AR-claim", terms=[immediate])).terms[0].value is None


class TestTransfer:
    """The note of a conversation that went to a person without a case handoff (POL-01)."""

    def test_the_example_is_valid_and_never_carries_the_transcript(self):
        note = Transfer.model_validate(TRANSFER)
        assert note.pending_action_not_run == "register_dispute" and note.charges[0].fraud_score_band == "<=30"
        assert not {"transcript", "messages", "text"} & set(Transfer.model_fields)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("transfer_id", "DSP-000001"),
            ("reason", "customer_was_rude"),
            ("requires_pt_analyst", True),
            ("pending_action_not_run", "refund"),
            ("rules_applied", ["RULE-1"]),
            ("transcript", "hola"),
        ],
    )
    def test_invalid_notes_are_rejected(self, field: str, value):
        with pytest.raises(ValidationError):
            Transfer.model_validate(TRANSFER | {field: value})
