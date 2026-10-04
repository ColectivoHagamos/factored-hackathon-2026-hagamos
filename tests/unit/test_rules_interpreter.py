"""Tests of the rules interpreter, the baseline: Spanish and Portuguese messages and their closed-schema fields."""

from decimal import Decimal

import pytest

from vera.llm.rules_adapter import RulesInterpreter

RULES = RulesInterpreter()


def read(text: str, **context: str):
    return RULES.interpret(text, context)


@pytest.mark.parametrize(
    ("text", "claim", "language"),
    [
        ("No reconozco un cargo de Uber de ayer", "unrecognized_charge", "es"),
        ("Hola, tengo una compra que no hice en Rappi", "unrecognized_charge", "es"),
        ("Não reconheço uma compra no cartão", "unrecognized_charge", "pt"),
        ("Me cobraron una comisión que no corresponde", "improper_charge", "es"),
        ("Hay un cobro duplicado en mi resumen", "improper_charge", "es"),
        ("Me llamaron del banco y transferí 500 dólares, me engañaron", "scam_transfer", "es"),
        ("Quiero hablar con una persona", "human_request", "es"),
        ("Quero falar com alguém, por favor", "human_request", "pt"),
        ("¿Cuál es mi saldo?", "out_of_scope", "es"),
        ("¿Y cuánto debo de la tarjeta?", "out_of_scope", "es"),
        ("Quanto devo no cartão?", "out_of_scope", "pt"),
        ("Fiz um Pix errado", "out_of_scope", "pt"),
        ("Me cobraron algo raro", "unrecognized_charge", "es"),
        ("Hay un movimiento sospechoso, yo no autoricé esa compra", "unrecognized_charge", "es"),
        ("Apareceu uma cobrança estranha no meu cartão", "unrecognized_charge", "pt"),
    ],
)
def test_claim_type_and_language(text: str, claim: str, language: str):
    result = read(text)
    assert (result.claim_type, result.language) == (claim, language)
    assert result.confidence >= 0.85


def test_unclear_message_has_low_confidence_so_the_flow_asks():
    result = read("buenas tardes")
    assert result.confidence < 0.6


def test_human_request_wins_over_any_claim():
    result = read("No reconozco un cargo, pero quiero una persona")
    assert result.claim_type == "human_request" and result.confidence >= 0.9


@pytest.mark.parametrize(
    ("text", "amount", "currency"),
    [
        ("un cargo de 120.000 pesos", Decimal("120000"), None),
        ("me cobraron 45,50 dólares", Decimal("45.50"), "USD"),
        ("fueron USD 87.50", Decimal("87.50"), "USD"),
        ("una compra de $35.000", Decimal("35000"), None),
        ("el 2 de junio", None, None),
        ("hace 3 días", None, None),
    ],
)
def test_amounts_are_read_only_when_they_are_money(text: str, amount, currency):
    result = read(text)
    assert (result.amount, result.currency) == (amount, currency)


def test_merchant_date_channel_and_card():
    result = read("No reconozco una compra en Super Ahorro de ayer por internet; no tengo la tarjeta")
    assert result.merchant_text == "Super Ahorro"
    assert result.date_text == "ayer"
    assert result.declared_channel == "online"
    assert result.has_card == "no"


def test_coercion_regulator_and_pix_flags():
    assert read("me están obligando a hacer esto").coercion
    assert read("voy a ir a la CONDUSEF").regulator_mentioned
    assert read("fiz um pix para outra conta").pix_mentioned


@pytest.mark.parametrize(("text", "answer"), [("sí, por favor", "yes"), ("Sim", "yes"), ("no", "no"), ("não", "no")])
def test_yes_or_no_answers(text: str, answer: str):
    assert read(text).answer == answer


def test_option_numbers_only_when_a_choice_was_asked():
    assert read("el 2 y el 3", expecting="choice").selected_numbers == (2, 3)
    assert read("la segunda", expecting="choice").selected_numbers == (2,)
    assert read("el 2 y el 3").selected_numbers == ()


def test_language_of_the_conversation_is_kept_for_neutral_messages():
    assert read("ok", language="pt").language == "pt"
