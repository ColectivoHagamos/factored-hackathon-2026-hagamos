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
        ("Quero o meu saldo e as minhas faturas", "out_of_scope", "pt"),
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


@pytest.mark.parametrize(
    "text",
    [
        "me están obligando a hacer esto",
        "Me están amenazando para que haga esto",
        "Me forzaron a dar la clave",
        "Me obrigaram a fazer a transferência",
        "Estou sendo ameaçado, me ajude",
    ],
)
def test_coercion_in_any_tense_is_a_threat(text: str):
    assert read(text).coercion


@pytest.mark.parametrize(
    ("text", "claim"),
    [
        ("Le transferí a un supuesto ejecutivo del banco, era una estafa", "scam_transfer"),
        ("Una persona me llamó diciendo que era del banco y le transferí mis ahorros", "scam_transfer"),
        ("Um falso gerente me ligou e eu transferi o dinheiro", "scam_transfer"),
        ("Me estafaron con una transferencia y quiero hablar con un asesor", "human_request"),
        ("Caí num golpe, quero falar com uma pessoa", "human_request"),
    ],
)
def test_a_role_in_a_scam_story_is_not_a_request_unless_the_customer_asks(text: str, claim: str):
    assert read(text).claim_type == claim


@pytest.mark.parametrize(
    ("text", "channel"),
    [
        ("Ayer me llamaron del banco", "phone_call"),
        ("me escribieron por WhatsApp", "message"),
        ("Ontem me ligaram", "phone_call"),
        ("por un link que me mandaron al correo", "email"),
        ("lo vi en Facebook", "social_media"),
        ("me llamo [name] y no reconozco un cargo", None),
    ],
)
def test_how_a_third_party_reached_the_customer(text: str, channel: str | None):
    assert read(text).contact_channel == channel


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


@pytest.mark.parametrize(
    ("text", "merchant"),
    [
        ("Revisando la app vi Libreria Andina en mis compras y no fui yo", "Libreria Andina"),
        ("Hola, Farmacia Uno me cobró de más", "Farmacia Uno"),
        ("Necesito ayuda. Mercado Libre me cobró dos veces", "Mercado Libre"),
        ("Me cobraron algo en Cine Estrella, no fui yo", "Cine Estrella"),
        ("No reconozco un cargo de mi tarjeta", None),
        ("Fue el 5 de Junio por la tarde", None),
        ("Buenas tardes, quiero reclamar", None),
    ],
)
def test_the_merchant_is_found_wherever_the_customer_names_it(text: str, merchant: str | None):
    assert read(text).merchant_text == merchant


@pytest.mark.parametrize(
    "text",
    [
        "¿Me pasas con alguien del banco?",
        "Necesito hablar con alguien ya",
        "Comuníqueme con servicio al cliente",
        "Quero falar com alguém da central",
        "Me passa pra alguém, por favor",
    ],
)
def test_more_ways_to_ask_for_a_person(text: str):
    assert read(text).claim_type == "human_request"


def test_a_scam_story_about_someone_from_the_bank_is_not_a_request_for_a_person():
    assert read("Hablé con alguien del banco por teléfono y me engañaron").claim_type == "scam_transfer"


@pytest.mark.parametrize(
    ("text", "claim"),
    [
        ("¿Eres una persona?", "unrecognized_charge"),
        ("¿Es usted un robot?", "unrecognized_charge"),
        ("Você é uma pessoa?", "unrecognized_charge"),
        ("¿Eres una persona? Quiero hablar con una persona", "human_request"),
    ],
)
def test_asking_whether_vera_is_a_person_is_not_asking_for_one(text: str, claim: str):
    reading = read(text)
    assert reading.asks_if_human and reading.claim_type == claim
