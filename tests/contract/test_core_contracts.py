"""Contract tests for the core boundary models: valid examples pass and invalid ones fail."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from vera.contracts.cases import Case
from vera.contracts.charges import Candidate, ChargeDetail
from vera.contracts.common import Money
from vera.contracts.events import Event
from vera.contracts.interpretation import Answer, ClaimType, Interpretation

HASH_A = "a" * 64
HASH_B = "b" * 64


def purchase(n: int = 1, amount: str = "120000", currency: str = "COP", status: str = "approved") -> dict:
    return {
        "n": n,
        "kind": "purchase",
        "occurred_at": "2026-06-14T21:05:00",
        "amount": amount,
        "currency": currency,
        "merchant": "Uber",
        "merchant_category": "Transport",
        "city": "Sao Paulo",
        "country": "Brazil",
        "status": status,
        "card": "•••• 1234",
    }


def case(charges: list[dict], exposure: list[dict]) -> dict:
    return {
        "case_id": "DSP-000123",
        "conversation_id": "conv-1",
        "status": "registered",
        "claim_type": "unrecognized_charge",
        "reason": "fraud",
        "declared_channel": "online",
        "charges": charges,
        "total_exposure": exposure,
        "total_exposure_usd": "46.25",
        "created_at": "2026-06-18T10:42:00-05:00",
    }


class TestInterpretation:
    def test_minimal_message_is_valid_and_defaults_are_conservative(self):
        result = Interpretation(claim_type="unrecognized_charge", language="pt", confidence=0.82)
        assert result.claim_type is ClaimType.UNRECOGNIZED_CHARGE
        assert result.has_card is Answer.NOT_SAID
        assert result.coercion is False

    @pytest.mark.parametrize(
        "fields",
        [
            {"claim_type": "refund_now"},
            {"confidence": 1.5},
            {"language": "en"},
            {"has_card": "maybe"},
            {"merchant_text": "x" * 201},
            {"tool_call": "block_card"},
        ],
    )
    def test_out_of_schema_output_is_rejected(self, fields: dict):
        base = {"claim_type": "improper_charge", "language": "es", "confidence": 0.9}
        with pytest.raises(ValidationError):
            Interpretation(**(base | fields))

    def test_instances_are_immutable(self):
        result = Interpretation(claim_type="out_of_scope", language="es", confidence=0.7)
        with pytest.raises(ValidationError):
            result.confidence = 0.1


class TestCandidate:
    def test_purchase_with_masked_card_is_valid(self):
        candidate = Candidate(**purchase())
        assert candidate.amount == Decimal("120000")

    def test_purchase_without_card_is_rejected(self):
        with pytest.raises(ValidationError, match="masked card"):
            Candidate(**(purchase() | {"card": None}))

    def test_bank_adjustment_may_have_no_card_or_merchant(self):
        adjustment = {"n": 2, "kind": "bank_adjustment", "occurred_at": "2026-06-01T00:00:00"}
        candidate = Candidate(**adjustment, amount="35.00", currency="USD", status="approved")
        assert candidate.card is None and candidate.merchant is None

    @pytest.mark.parametrize("card", ["4111" + "1111" * 3, "**** 1234", "•••• 12345"])
    def test_only_masked_cards_are_accepted(self, card: str):
        with pytest.raises(ValidationError):
            Candidate(**(purchase() | {"card": card}))

    @pytest.mark.parametrize("amount", ["-1", "10.005"])
    def test_invalid_amounts_are_rejected(self, amount: str):
        with pytest.raises(ValidationError):
            Candidate(**purchase(amount=amount))

    def test_detail_carries_the_score_band_but_never_the_fraud_label(self):
        assert ChargeDetail(**purchase(), fraud_score_band=">30").fraud_score_band == ">30"
        with pytest.raises(ValidationError):
            ChargeDetail(**purchase(), fraud_score_band=">30", is_fraud=True)


class TestEvent:
    def test_first_event_has_no_previous_hash(self):
        event = Event(
            event_id="evt-1",
            conversation_id="conv-1",
            ts=datetime(2026, 6, 18, 15, 42, tzinfo=UTC),
            type="rule_decision",
            data={"rule": "POL-06", "version": "1.4", "result": "escalate"},
            prev_hash=None,
            hash=HASH_A,
        )
        assert event.llm_provider is None

    @pytest.mark.parametrize(
        "fields",
        [
            {"ts": "2026-06-18T10:42:00"},
            {"type": "money_moved"},
            {"hash": "not-a-hash"},
            {"conversation_id": "conv 1; drop"},
        ],
    )
    def test_invalid_events_are_rejected(self, fields: dict):
        base = {
            "event_id": "evt-2",
            "conversation_id": "conv-1",
            "ts": "2026-06-18T10:42:00-05:00",
            "type": "reply",
            "data": {},
            "prev_hash": HASH_A,
            "hash": HASH_B,
        }
        with pytest.raises(ValidationError):
            Event(**(base | fields))


class TestCase:
    def test_exposure_is_the_sum_of_approved_charges_per_currency(self):
        charges = [purchase(1, "120000"), purchase(2, "65000"), purchase(3, "20", "USD")]
        exposure = [{"amount": "185000", "currency": "COP"}, {"amount": "20", "currency": "USD"}]
        assert Case(**case(charges, exposure)).total_exposure[0] == Money(amount=Decimal("185000"), currency="COP")

    def test_pending_charge_stays_in_the_case_without_adding_to_exposure(self):
        charges = [purchase(1, "120000"), purchase(2, "50000", status="pending")]
        assert Case(**case(charges, [{"amount": "120000", "currency": "COP"}])).charges[1].status == "pending"

    @pytest.mark.parametrize(
        "exposure",
        [
            [{"amount": "160000", "currency": "COP"}],
            [{"amount": "120000", "currency": "COP"}, {"amount": "50000", "currency": "COP"}],
            [],
        ],
    )
    def test_inconsistent_exposure_is_rejected(self, exposure: list[dict]):
        with pytest.raises(ValidationError, match="total_exposure"):
            Case(**case([purchase(1, "120000"), purchase(2, "50000")], exposure))

    def test_a_charge_cannot_appear_twice(self):
        with pytest.raises(ValidationError, match="once"):
            Case(**case([purchase(1), purchase(1)], [{"amount": "240000", "currency": "COP"}]))

    @pytest.mark.parametrize("case_id", ["DSP-123", "dsp-000123", "DSP-0001234"])
    def test_case_id_format(self, case_id: str):
        with pytest.raises(ValidationError):
            Case(**(case([purchase()], [{"amount": "120000", "currency": "COP"}]) | {"case_id": case_id}))
