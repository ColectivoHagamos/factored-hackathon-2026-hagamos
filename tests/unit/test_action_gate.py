"""Tests of the action gate (P17): token bound to the exact arguments, single use, expiry and read-back."""

from datetime import date, timedelta

import pytest

from vera.adapters.mock_bank import CLOCK, MockBank
from vera.adapters.sqlite_state import SqliteState
from vera.contracts.tools import TOOL_INPUTS, BlockCardInput, RegisterDisputeInput, SearchChargesInput
from vera.policy.model import load_policy
from vera.tools.gate import RISK_TABLE, ActionGate
from vera.tools.toolbox import Offers, Session, Toolbox

PENDING = "tok_pending_confirmation"
SESSION = Session("CUS-MOCK00000000002", "conv-1")


class Clock:
    def __init__(self) -> None:
        self.now = CLOCK

    def __call__(self):
        return self.now


@pytest.fixture
def world():
    state = SqliteState()
    bank = MockBank(state)
    clock = Clock()
    tools = Toolbox(bank, bank, state, state, load_policy().parameters.usd_rates, now=clock)
    gate = ActionGate(tools, secret=b"test-secret", now=clock)
    _, offers = tools.search_charges(
        SESSION, Offers(), SearchChargesInput(date_from=date(2026, 6, 1), date_to=date(2026, 6, 18))
    )
    return state, bank, clock, tools, gate, offers


def dispute(charges: list[int], token: str = PENDING) -> RegisterDisputeInput:
    return RegisterDisputeInput(charges_n=charges, reason="fraud", declared_channel="online", confirmation_token=token)


def confirmed(gate: ActionGate, args: RegisterDisputeInput, session: Session = SESSION) -> RegisterDisputeInput:
    token = gate.confirm(session, "register_dispute", args).token
    return args.model_copy(update={"confirmation_token": token})


def test_a_confirmed_write_runs_once_and_is_read_back(world):
    state, *_, gate, offers = world
    result = gate.register_dispute(SESSION, offers, confirmed(gate, dispute([2, 3])), claim_type="unrecognized_charge")
    assert result.read_back_matches and result.output.case_id == "DSP-000001"
    assert state.cases_of(SESSION.customer_ref) == ("DSP-000001",)


@pytest.mark.parametrize("token", [PENDING, "tok_9999999999_" + "0" * 40, "not-a-valid-token-at-all"])
def test_a_write_without_a_valid_token_fails_and_writes_nothing(world, token: str):
    state, *_, gate, offers = world
    result = gate.register_dispute(SESSION, offers, dispute([2], token), claim_type="unrecognized_charge")
    assert result.output.code == "invalid_token" and not result.read_back_matches
    assert state.cases_of(SESSION.customer_ref) == ()


def test_a_token_cannot_be_used_twice(world):
    *_, gate, offers = world
    args = confirmed(gate, dispute([2]))
    assert gate.register_dispute(SESSION, offers, args, claim_type="unrecognized_charge").read_back_matches
    assert gate.register_dispute(SESSION, offers, args, claim_type="unrecognized_charge").output.code == "invalid_token"


def test_changing_the_arguments_invalidates_the_token(world):
    state, *_, gate, offers = world
    args = confirmed(gate, dispute([2]))
    tampered = args.model_copy(update={"charges_n": (2, 3)})
    assert (
        gate.register_dispute(SESSION, offers, tampered, claim_type="unrecognized_charge").output.code
        == "invalid_token"
    )
    assert state.cases_of(SESSION.customer_ref) == ()


def test_a_token_expires_and_belongs_to_one_conversation(world):
    _, _, clock, _, gate, offers = world
    args = confirmed(gate, dispute([2]))
    other = Session(SESSION.customer_ref, "conv-2")
    assert gate.register_dispute(other, offers, args, claim_type="unrecognized_charge").output.code == "invalid_token"
    clock.now = CLOCK + timedelta(minutes=11)
    assert gate.register_dispute(SESSION, offers, args, claim_type="unrecognized_charge").output.code == "invalid_token"


def test_blocking_reports_success_only_after_reading_the_card_back(world):
    _, bank, _, tools, gate, offers = world
    block = BlockCardInput(card_n=1, confirmation_token=PENDING)
    token = gate.confirm(SESSION, "block_card", block).token
    assert gate.block_card(SESSION, offers, block.model_copy(update={"confirmation_token": token})).read_back_matches
    # A card system that silently ignores the block is caught by the read-back.
    bank.block = lambda card_ref, idempotency_key: None
    other = Session("CUS-MOCK00000000001", "conv-3")
    _, other_offers = tools.search_charges(
        other, Offers(), SearchChargesInput(date_from=date(2026, 6, 1), date_to=date(2026, 6, 18))
    )
    token = gate.confirm(other, "block_card", block).token
    result = gate.block_card(other, other_offers, block.model_copy(update={"confirmation_token": token}))
    assert result.output.status == "blocked" and not result.read_back_matches


def test_risk_table_covers_every_tool_and_reads_need_no_confirmation(world):
    *_, gate, _ = world
    assert set(RISK_TABLE) == set(TOOL_INPUTS)
    with pytest.raises(ValueError, match="does not take a confirmation"):
        gate.confirm(
            SESSION, "search_charges", SearchChargesInput(date_from=date(2026, 6, 1), date_to=date(2026, 6, 2))
        )
