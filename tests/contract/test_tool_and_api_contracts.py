"""Contract tests for the tool and API models, and for the exported JSON Schemas."""

import pytest
from pydantic import ValidationError

from scripts.export_schemas import differences, expected_files
from vera.contracts.api import ApiError, GlassBoxEntry, MessageRequest
from vera.contracts.tools import (
    TOOL_INPUTS,
    TOOL_OUTPUTS,
    BlockCardInput,
    RegisterDisputeInput,
    SearchChargesInput,
    ToolError,
)

TOKEN = "tok_" + "a1b2c3d4" * 3


class TestTools:
    def test_the_design_tools_and_no_money_tool(self):
        expected = {
            "search_charges",
            "view_charge",
            "sweep_charges",
            "block_card",
            "register_dispute",
            "read_case",
            "create_handoff",
            "send_fraud_alert",
        }
        assert set(TOOL_INPUTS) == set(TOOL_OUTPUTS) == expected

    @pytest.mark.parametrize("field", ["customer_id", "customer", "document_number"])
    def test_customer_never_comes_from_an_argument(self, field: str):
        with pytest.raises(ValidationError):
            SearchChargesInput(date_from="2026-06-01", date_to="2026-06-18", **{field: "C-1"})

    def test_search_range_must_be_ordered(self):
        with pytest.raises(ValidationError, match="date_from"):
            SearchChargesInput(date_from="2026-06-18", date_to="2026-06-01")

    def test_register_dispute_takes_numbers_and_a_token_but_no_amount(self):
        valid = {"charges_n": [1, 3], "reason": "fraud", "declared_channel": "online", "confirmation_token": TOKEN}
        assert RegisterDisputeInput(**valid).charges_n == (1, 3)
        for invalid in ({"amount": "185000"}, {"charges_n": [1, 1]}, {"charges_n": []}, {"confirmation_token": "x"}):
            with pytest.raises(ValidationError):
                RegisterDisputeInput(**(valid | invalid))

    def test_block_card_requires_a_confirmation_token(self):
        with pytest.raises(ValidationError):
            BlockCardInput(card_n=1)

    def test_duplicate_returns_the_existing_case_and_only_then(self):
        assert ToolError(code="duplicate", case_id="DSP-000123").case_id == "DSP-000123"
        with pytest.raises(ValidationError):
            ToolError(code="duplicate")
        with pytest.raises(ValidationError):
            ToolError(code="not_found", case_id="DSP-000123")


class TestApi:
    @pytest.mark.parametrize(
        "body", [{"text": "No reconozco un cargo"}, {"selected_option": 2}, {"selected_option": "yes"}]
    )
    def test_message_has_exactly_one_input(self, body: dict):
        assert MessageRequest(**body)

    @pytest.mark.parametrize(
        "body",
        [{}, {"text": "hola", "selected_option": 1}, {"selected_option": "maybe"}, {"text": "x" * 2001}],
    )
    def test_invalid_messages_are_rejected(self, body: dict):
        with pytest.raises(ValidationError):
            MessageRequest(**body)

    @pytest.mark.parametrize("rule_id", ["POL-07", "PROH-03", "CO-R15", "BR-R01"])
    def test_glass_box_cites_policy_or_legal_rules(self, rule_id: str):
        assert GlassBoxEntry(rule_id=rule_id, source="Master policy v1.4").rule_id == rule_id

    def test_glass_box_rejects_free_text_rule_ids(self):
        with pytest.raises(ValidationError):
            GlassBoxEntry(rule_id="rule 7", source="model")

    def test_errors_use_closed_codes(self):
        assert ApiError(code="not_found", message="Case not found").code == "not_found"
        with pytest.raises(ValidationError):
            ApiError(code="forbidden_other_customer", message="x")


def test_exported_schemas_match_the_models():
    assert differences(expected_files()) == [], "Run: python -m scripts.export_schemas"
