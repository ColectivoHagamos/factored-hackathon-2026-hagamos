"""Tests of the tools on the mock bank: numbered options, exposure, idempotency and duplicates."""

from datetime import date
from decimal import Decimal

import pytest

from vera.adapters.mock_bank import CLOCK, MockBank
from vera.adapters.sqlite_state import SqliteState
from vera.contracts.handoff import Handoff
from vera.contracts.tools import (
    BlockCardInput,
    CreateHandoffInput,
    ReadCaseInput,
    RegisterDisputeInput,
    SearchChargesInput,
    SweepChargesInput,
    ToolError,
    ViewChargeInput,
)
from vera.policy.model import load_policy
from vera.ports.tools import Offers, Session
from vera.tools.toolbox import Toolbox

TOKEN = "tok_" + "a1b2c3d4" * 3
CO_02 = Session("CUS-MOCK00000000002", "conv-1")


@pytest.fixture
def tools() -> Toolbox:
    state = SqliteState()
    bank = MockBank(state)
    return Toolbox(bank, bank, state, state, load_policy().parameters.usd_rates, now=lambda: CLOCK)


def search(tools: Toolbox, session: Session = CO_02, offers: Offers | None = None, **filters):
    args = SearchChargesInput(date_from=date(2026, 6, 1), date_to=date(2026, 6, 18), **filters)
    return tools.search_charges(session, offers or Offers(), args)


def test_search_offers_numbered_candidates_most_recent_first(tools: Toolbox):
    output, offers = search(tools)
    assert [c.n for c in output.candidates] == [1, 2, 3]
    assert output.candidates[0].status == "pending" and output.candidates[0].card == "•••• 7310"
    assert set(offers.charges) == {1, 2, 3} and offers.cards == {1: "PRD-MOCK00000000021"}


def test_search_filters_by_merchant_and_amount(tools: Toolbox):
    output, _ = search(tools, merchant="uber")
    assert [c.merchant for c in output.candidates] == ["Uber", "Uber"]
    output, _ = search(tools, amount=Decimal("120000"))
    assert [c.amount for c in output.candidates] == [Decimal("120000")]
    assert search(tools, merchant="Unknown Shop").code == "no_results"


def test_numbers_stay_stable_across_search_and_sweep(tools: Toolbox):
    first, offers = search(tools, merchant="uber")
    oldest = min(first.candidates, key=lambda c: c.occurred_at)
    swept, offers = tools.sweep_charges(CO_02, offers, SweepChargesInput(candidate_n=oldest.n))
    numbers = {c.occurred_at: c.n for c in swept.charges}
    assert all(numbers[c.occurred_at] == c.n for c in first.candidates)
    assert any(c.status == "pending" for c in swept.charges)


def test_view_charge_shows_the_score_band_only_for_offered_numbers(tools: Toolbox):
    _, offers = search(tools, merchant="uber")
    detail = tools.view_charge(CO_02, offers, ViewChargeInput(candidate_n=2))
    assert detail.fraud_score_band == ">30"
    assert tools.view_charge(CO_02, offers, ViewChargeInput(candidate_n=9)).code == "not_found"


def test_register_dispute_sums_approved_charges_and_is_idempotent(tools: Toolbox):
    _, offers = search(tools)
    args = RegisterDisputeInput(
        charges_n=[1, 2, 3], reason="fraud", declared_channel="online", confirmation_token=TOKEN
    )
    first = tools.register_dispute(CO_02, offers, args, claim_type="unrecognized_charge")
    # The pending charge stays in the case without adding to the exposure.
    assert [(m.currency, m.amount) for m in first.total_exposure] == [("COP", Decimal("185000"))]
    again = tools.register_dispute(CO_02, offers, args, claim_type="unrecognized_charge")
    assert again.case_id == first.case_id
    case = tools.read_case(CO_02, ReadCaseInput(case_id=first.case_id))
    assert case.total_exposure_usd == Decimal("46.25") and len(case.charges) == 3


def test_disputing_a_charge_again_in_another_conversation_returns_the_existing_case(tools: Toolbox):
    _, offers = search(tools, merchant="uber")
    args = RegisterDisputeInput(charges_n=[1], reason="fraud", declared_channel="online", confirmation_token=TOKEN)
    case_id = tools.register_dispute(CO_02, offers, args, claim_type="unrecognized_charge").case_id
    other = Session(CO_02.customer_ref, "conv-2")
    _, offers_2 = search(tools, session=other, merchant="uber")
    duplicate = tools.register_dispute(other, offers_2, args, claim_type="unrecognized_charge")
    assert isinstance(duplicate, ToolError) and (duplicate.code, duplicate.case_id) == ("duplicate", case_id)


def test_block_card_only_for_offered_cards_and_twice_is_still_a_success(tools: Toolbox):
    assert tools.block_card(CO_02, Offers(), BlockCardInput(card_n=1, confirmation_token=TOKEN)).code == "not_found"
    _, offers = search(tools)
    assert tools.block_card(CO_02, offers, BlockCardInput(card_n=1, confirmation_token=TOKEN)).status == "blocked"
    assert tools.card_status(CO_02, offers, 1) == "blocked"
    assert tools.block_card(CO_02, offers, BlockCardInput(card_n=1, confirmation_token=TOKEN)).status == "blocked"


def test_handoff_is_created_only_for_a_case_of_the_session(tools: Toolbox, handoff_example: Handoff):
    _, offers = search(tools, merchant="uber")
    args = RegisterDisputeInput(charges_n=[1, 2], reason="fraud", declared_channel="online", confirmation_token=TOKEN)
    case_id = tools.register_dispute(CO_02, offers, args, claim_type="unrecognized_charge").case_id
    handoff = handoff_example.model_copy(update={"case_id": case_id})
    created = tools.create_handoff(CO_02, CreateHandoffInput(case_id=case_id, queue="fraud"), handoff)
    assert created.handoff_id.startswith("HND-")
    stranger = Session("CUS-MOCK00000000001", "conv-9")
    assert (
        tools.create_handoff(stranger, CreateHandoffInput(case_id=case_id, queue="fraud"), handoff).code == "not_found"
    )


@pytest.fixture
def handoff_example() -> Handoff:
    import json
    from pathlib import Path

    path = Path(__file__).parents[1] / "contract" / "examples" / "handoff.json"
    return Handoff.model_validate(json.loads(path.read_text(encoding="utf-8")))
