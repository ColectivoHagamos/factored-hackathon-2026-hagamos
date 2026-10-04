"""Tests of the conversation flow (P15) on the mock bank with the rules interpreter, end to end in memory."""

from itertools import count

import pytest

from vera.adapters.memory_event_log import MemoryEventLog
from vera.adapters.mock_bank import CLOCK, MockBank
from vera.adapters.sqlite_state import SqliteState
from vera.contracts.api import MessageRequest
from vera.core.events import reduce, verify_chain
from vera.core.flow import Conversation
from vera.core.state import FlowState, Step
from vera.llm.rules_adapter import RulesInterpreter
from vera.output.render import Renderer
from vera.policy.engine import PolicyEngine
from vera.policy.legal_clock import LegalClock
from vera.policy.model import load_policy
from vera.ports.tools import Session
from vera.tools.gate import ActionGate
from vera.tools.service import ToolService
from vera.tools.toolbox import Toolbox

POLICY = load_policy()
CO_01, CO_02, AR_01 = "CUS-MOCK00000000001", "CUS-MOCK00000000002", "CUS-MOCK00000000004"


class World:
    def __init__(self) -> None:
        self.state = SqliteState()
        bank = MockBank(self.state)
        now = lambda: CLOCK  # noqa: E731
        toolbox = Toolbox(bank, bank, self.state, self.state, POLICY.parameters.usd_rates, now=now)
        tools = ToolService(toolbox, ActionGate(toolbox, b"secret", now=now), bank, bank, now=now)
        ids = count(1)
        self.log = MemoryEventLog()
        self.conversation = Conversation(
            interpreter=RulesInterpreter(),
            tools=tools,
            log=self.log,
            engine=PolicyEngine(POLICY),
            legal=LegalClock.from_files(),
            renderer=Renderer(),
            now=now,
            new_id=lambda: f"evt-{next(ids)}",
        )

    def chat(self, customer: str, *messages: str | int, conversation_id: str = "conv-1"):
        session = Session(customer, conversation_id)
        replies = [self.conversation.start(session)]
        for message in messages:
            body = MessageRequest(selected_option=message) if isinstance(message, int) else MessageRequest(text=message)
            replies.append(self.conversation.reply(session, body))
        return replies

    def state_of(self, conversation_id: str = "conv-1") -> FlowState:
        last = [e for e in self.log.read(conversation_id) if e.type == "reply"][-1]
        return FlowState.model_validate(last.data["state"])


@pytest.fixture
def world() -> World:
    return World()


def test_a1_purchase_in_colombia_is_registered_read_back_and_dated(world: World):
    replies = world.chat(CO_01, "No reconozco un cargo de Libreria Andina", "no", "sí", "sí, la tengo", "todos", "sí")
    greeting, receipt, channel, card, sweep, confirm, done = replies
    assert "inteligencia artificial" in greeting and "persona" in greeting
    assert "Libreria Andina" in receipt.reply and "COP 185.000" in receipt.reply and "¿Reconoce" in receipt.reply
    assert "internet" in channel.reply and "¿Tiene la tarjeta" in card.reply
    assert "Cafe del Parque" in sweep.options[0].label
    assert confirm.pending_confirmation.action == "register_dispute" and "COP 185.000" in confirm.reply
    assert "DSP-000001" in done.reply and "3 de julio de 2026" in done.reply
    assert "Reversión del pago" in done.reply
    assert any(entry.rule_id == "CO-R15" and entry.deadline.isoformat() == "2026-07-03" for entry in done.glass_box)
    assert world.state_of().step is Step.DONE
    events = world.log.read("conv-1")
    verify_chain(events)
    assert len(reduce("conv-1", events).completed_actions) == 1


def test_a3_signals_lead_to_a_confirmed_block_one_case_and_a_fraud_handoff(world: World):
    replies = world.chat(
        CO_02, "No reconozco un cargo de Uber", 2, "no", "sí", "no tengo la tarjeta", "no reconozco ninguno", "sí", "sí"
    )
    choose, block_offer, register_offer, done = replies[1], replies[6], replies[7], replies[8]
    assert len(choose.options) == 2
    assert block_offer.pending_confirmation.action == "block_card" and "•••• 7310" in block_offer.reply
    assert "quedó bloqueada" in register_offer.reply and "COP 185.000" in register_offer.reply
    assert "analista" in done.reply
    state = world.state_of()
    assert state.step is Step.HANDED_OFF and state.queue == "fraud"
    handoff = world.state.handoff_of(state.case_id)
    assert handoff.response_level == 3 and handoff.fraud_alert and handoff.suggested_queue == "fraud"
    assert handoff.network_clock.suggested_code == "10.4"
    assert {a.action for a in handoff.actions} == {"block_card", "register_dispute"}
    assert "card_not_in_possession" in handoff.risk_signals


def test_a2_pending_charge_is_explained_and_closed_when_recognized(world: World):
    _, receipt, closing = world.chat(CO_02, "No reconozco un cargo de Farmacia Salud", "sí")
    assert "pendiente" in receipt.reply
    assert "no hace falta abrir un reclamo" in closing.reply
    assert world.state_of().step is Step.DONE
    assert world.state.cases_of(CO_02) == ()


def test_a8_a_person_wins_at_any_step(world: World):
    _, receipt, human = world.chat(CO_01, "No reconozco un cargo de Libreria Andina", "quiero hablar con una persona")
    assert "una persona" in human.reply
    assert any(entry.rule_id == "POL-01" for entry in human.glass_box)
    assert world.state_of().step is Step.HANDED_OFF


def test_out_of_scope_is_oriented_without_opening_anything(world: World):
    _, reply = world.chat(CO_01, "¿Cuál es mi saldo?")
    assert "saldo" in reply.reply and world.state_of().step is Step.ASK_CLAIM


def test_portuguese_customer_is_answered_in_portuguese(world: World):
    _, reply = world.chat(CO_02, "Não reconheço uma compra da Farmacia Salud")
    assert "Situação: pendente" in reply.reply and world.state_of().variant == "pt"


def test_a_loop_of_unclear_messages_ends_with_a_person(world: World):
    replies = world.chat(AR_01, "hola", "mmm", "no sé")
    assert "persona" in replies[-1].reply
    assert world.state_of().step is Step.HANDED_OFF


def test_argentina_offers_the_block_only_at_the_customers_request(world: World):
    replies = world.chat(
        AR_01, "No reconozco un cargo de Electro Sur", 2, "no", "sí", "no tengo la tarjeta", "no reconozco ninguno"
    )
    assert replies[-1].pending_confirmation.action == "block_card"
    assert "no exige bloquear" in replies[-1].reply


def test_yes_and_no_buttons_answer_the_pending_question(world: World):
    session = Session(CO_02, "conv-buttons")
    world.conversation.start(session)
    receipt = world.conversation.reply(session, MessageRequest(text="No reconozco un cargo de Farmacia Salud"))
    assert [option.answer for option in receipt.options] == ["yes", "no"]
    closing = world.conversation.reply(session, MessageRequest(selected_option="yes"))
    assert "no hace falta abrir un reclamo" in closing.reply


def test_register_wording_follows_the_variant(world: World):
    *_, done = world.chat(CO_01, "No reconozco un cargo de Libreria Andina", "no", "sí", "sí, la tengo", "todos", "sí")
    assert "cuando quiera." in done.reply and "1 cargo por" not in done.reply
