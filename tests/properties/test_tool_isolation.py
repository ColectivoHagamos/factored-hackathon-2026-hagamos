"""Property tests: no tool ever shows data of another customer, and what is not offered reads as not found."""

from datetime import date
from itertools import permutations

import pytest

from vera.adapters.mock_bank import CLOCK, CUSTOMERS, MockBank
from vera.adapters.sqlite_state import SqliteState
from vera.contracts.tools import (
    BlockCardInput,
    ReadCaseInput,
    RegisterDisputeInput,
    SearchChargesInput,
    SendFraudAlertInput,
    SweepChargesInput,
    ToolError,
    ViewChargeInput,
)
from vera.policy.model import load_policy
from vera.ports.tools import Offers, Session
from vera.tools.toolbox import Toolbox

TOKEN = "tok_" + "a1b2c3d4" * 3
WINDOW = SearchChargesInput(date_from=date(2025, 1, 1), date_to=date(2026, 6, 18))


@pytest.fixture
def setup():
    state = SqliteState()
    bank = MockBank(state)
    return bank, Toolbox(bank, bank, state, state, load_policy().parameters.usd_rates, now=lambda: CLOCK)


@pytest.mark.parametrize("customer", CUSTOMERS, ids=lambda c: c.alias)
def test_search_only_ever_offers_charges_of_the_session_customer(setup, customer):
    bank, tools = setup
    session = Session(customer.customer_ref, "conv")
    result = tools.search_charges(session, Offers(), WINDOW)
    own = {c.charge_ref for c in bank.charges(customer.customer_ref, CLOCK.replace(year=2025), CLOCK)}
    if isinstance(result, ToolError):
        assert not own
        return
    _, offers = result
    assert set(offers.charges.values()) <= own


@pytest.mark.parametrize(("owner", "intruder"), list(permutations(CUSTOMERS[:3], 2)), ids=lambda c: c.alias)
def test_options_offered_to_one_customer_are_not_found_for_another(setup, owner, intruder):
    bank, tools = setup
    _, offers = tools.search_charges(Session(owner.customer_ref, "conv-a"), Offers(), WINDOW)
    stranger = Session(intruder.customer_ref, "conv-b")
    for n in offers.charges:
        assert tools.view_charge(stranger, offers, ViewChargeInput(candidate_n=n)).code == "not_found"
        assert tools.sweep_charges(stranger, offers, SweepChargesInput(candidate_n=n)).code == "not_found"
    for n in offers.cards:
        assert (
            tools.block_card(stranger, offers, BlockCardInput(card_n=n, confirmation_token=TOKEN)).code == "not_found"
        )
    args = RegisterDisputeInput(
        charges_n=list(offers.charges)[:1], reason="fraud", declared_channel="online", confirmation_token=TOKEN
    )
    assert tools.register_dispute(stranger, offers, args, claim_type="unrecognized_charge").code == "not_found"
    alert = SendFraudAlertInput(charges_n=list(offers.charges)[:1], signals=["new_merchant"], card_blocked=False)
    assert tools.send_fraud_alert(stranger, offers, alert).code == "not_found"


def test_a_case_of_another_customer_reads_exactly_like_a_missing_one(setup):
    bank, tools = setup
    owner = Session(CUSTOMERS[1].customer_ref, "conv-a")
    _, offers = tools.search_charges(owner, Offers(), WINDOW)
    args = RegisterDisputeInput(charges_n=[1], reason="fraud", declared_channel="online", confirmation_token=TOKEN)
    case_id = tools.register_dispute(owner, offers, args, claim_type="unrecognized_charge").case_id
    stranger = Session(CUSTOMERS[0].customer_ref, "conv-b")
    foreign = tools.read_case(stranger, ReadCaseInput(case_id=case_id))
    missing = tools.read_case(stranger, ReadCaseInput(case_id="DSP-999999"))
    assert foreign == missing == ToolError(code="not_found")


def test_a_fraud_alert_cannot_point_to_a_case_of_another_customer(setup):
    bank, tools = setup
    owner = Session(CUSTOMERS[1].customer_ref, "conv-a")
    _, offers = tools.search_charges(owner, Offers(), WINDOW)
    args = RegisterDisputeInput(charges_n=[1], reason="fraud", declared_channel="online", confirmation_token=TOKEN)
    case_id = tools.register_dispute(owner, offers, args, claim_type="unrecognized_charge").case_id
    stranger = Session(CUSTOMERS[0].customer_ref, "conv-b")
    _, own_offers = tools.search_charges(stranger, Offers(), WINDOW)
    alert = SendFraudAlertInput(charges_n=[1], signals=["new_merchant"], card_blocked=False, case_id=case_id)
    assert tools.send_fraud_alert(stranger, own_offers, alert) == ToolError(code="not_found")
