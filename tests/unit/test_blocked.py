"""A payment declined or a card blocked by the bank: VERA reads the movements and offers the person who can unblock.

Customers ask this in so many words ("¿por qué se bloqueó mi transacción?"), and a language model files it as out of
scope; the rules hear it underneath, and the flow answers with what the tools show instead of a generic reply.
"""

import pytest

from tests.llm_fake import WRONG, FakeMessages, reply
from tests.unit.test_flow import AR_01, CO_01, World
from vera.contracts.handoff import Queue, Transfer
from vera.core.state import Step
from vera.llm.anthropic_adapter import AnthropicInterpreter
from vera.llm.rules_adapter import RulesInterpreter

CLAIM = {"language": "es", "expecting": "claim"}


@pytest.mark.parametrize(
    "text",
    [
        "¿Por qué se bloqueó mi transacción?",
        "quiero saber porque se bloqueo mi tarjeta? la tengo yo y el movimiento es legal",
        "Me rechazaron una compra en el súper",
        "Mi tarjeta está bloqueada y no me deja pagar",
        "Minha compra foi recusada",
        "Meu cartão foi bloqueado",
    ],
)
def test_the_rules_hear_a_declined_payment_or_a_blocked_card(text: str):
    assert RulesInterpreter().interpret(text, CLAIM).blocked


@pytest.mark.parametrize(
    "text",
    ["Quiero bloquear mi tarjeta", "Bloquéala, por favor", "No reconozco un cargo de Uber", "¿Cuál es mi saldo?"],
)
def test_a_request_to_block_is_not_a_blocked_card(text: str):
    # Asking VERA to block the card is the lost-card path, never this one.
    assert not RulesInterpreter().interpret(text, CLAIM).blocked


def test_the_rules_keep_the_fact_when_the_model_files_it_as_out_of_scope():
    reading = AnthropicInterpreter(FakeMessages(reply(WRONG))).interpret("¿Por qué se bloqueó mi transacción?", CLAIM)
    assert reading.claim_type.value == "out_of_scope" and reading.blocked


def test_vera_shows_the_declined_attempt_and_hands_the_review_to_fraud():
    world = World()
    _, offer, done = world.chat(AR_01, "¿Por qué se bloqueó mi transacción?", "sí")
    assert "Electro Sur" in offer.reply and "rechazad" in offer.reply and "saldo" not in offer.reply
    assert [option.answer for option in offer.options] == ["yes", "no"]
    assert world.state_of().step is Step.HANDED_OFF and world.state_of().queue is Queue.FRAUD
    assert "Fraude" in done.reply
    notes = [item for item in world.state.queue() if isinstance(item, Transfer)]
    assert len(notes) == 1 and "Electro Sur" in notes[0].model_dump_json()


def test_without_declined_attempts_vera_says_so_and_still_offers_the_person():
    world = World()
    _, offer = world.chat(CO_01, "Me bloquearon la tarjeta")
    assert "no veo intentos rechazados" in offer.reply and world.state_of().step is Step.BLOCKED_OFFER


def test_declining_the_person_goes_back_to_the_menu():
    world = World()
    *_, back = world.chat(AR_01, "Me rechazaron una compra", "no")
    assert world.state_of().step is Step.ASK_CLAIM and len(back.options) == 5
    assert world.state_of().disputed == []


def test_a_claim_written_at_the_offer_goes_on_as_that_claim():
    world = World()
    world.chat(AR_01, "Me rechazaron una compra", "No reconozco un cargo de Electro Sur")
    assert world.state_of().step is not Step.BLOCKED_OFFER and world.state_of().claim_type is not None


def test_a_sure_dispute_that_mentions_a_block_stays_a_dispute():
    world = World()
    world.chat(AR_01, "No reconozco un cargo de Electro Sur y me bloquearon la tarjeta")
    assert world.state_of().step is not Step.BLOCKED_OFFER and world.state_of().claim_type is not None


def test_a_yes_takes_the_offer_even_when_the_reader_also_names_a_claim():
    # A language model must fill a claim type, and may read "sí" as a dispute: the yes still takes the offer.
    eager = {"claim_type": "unrecognized_charge", "answer": "yes", "language": "es", "confidence": 0.9}
    world = World(interpreter=AnthropicInterpreter(FakeMessages(reply(WRONG), reply(eager))))
    world.chat(AR_01, "¿Por qué se bloqueó mi transacción?", "sí")
    assert world.state_of().step is Step.HANDED_OFF and world.state_of().queue is Queue.FRAUD


def test_a_bare_no_declines_the_offer_even_when_the_reader_files_it_as_a_claim():
    eager = {"claim_type": "unrecognized_charge", "answer": "no", "language": "es", "confidence": 1.0}
    world = World(interpreter=AnthropicInterpreter(FakeMessages(reply(WRONG), reply(eager))))
    *_, back = world.chat(AR_01, "¿Por qué se bloqueó mi transacción?", "no")
    assert world.state_of().step is Step.ASK_CLAIM and len(back.options) == 5


def test_asking_for_the_person_at_the_offer_takes_it_without_a_second_offer():
    world = World()
    world.chat(AR_01, "¿Por qué se bloqueó mi transacción?", "Sí, quiero hablar con una persona")
    assert world.state_of().step is Step.HANDED_OFF and world.state_of().person_offers == 0
