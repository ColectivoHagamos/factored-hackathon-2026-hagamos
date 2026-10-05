"""Tests of the reply templates and the output validator (P18)."""

from datetime import date
from decimal import Decimal

import pytest

from vera.contracts.common import Currency, Language
from vera.contracts.handoff import LanguageVariant
from vera.output.render import Renderer, day, money
from vera.output.validator import UnsafeReplyError, check, violations

RENDERER = Renderer()
VALUES = {
    "who": ", Ana",
    "date": "14 de junio de 2026",
    "merchant": "Uber",
    "amount": "COP 120.000",
    "status": "aprobado",
    "card": "•••• 4821",
    "charges": "2 cargos",
    "exposure": "COP 185.000",
    "case_id": "DSP-000123",
    "rule": "Ley 1755 de 2015, art. 14",
    "what": "responder el reclamo",
    "route": "Reversión del pago",
    "venue": "la Superintendencia Financiera",
    "time": "21:00",
    "charge": "el cargo de Uber por COP 120.000 del 14 de junio de 2026 a las 21:00",
}
ALLOWED = frozenset({"COP 120.000", "COP 185.000"})


@pytest.mark.parametrize("variant", list(LanguageVariant))
def test_every_template_renders_in_every_variant_and_passes_the_validator(variant: LanguageVariant):
    language = Language.PT if variant is LanguageVariant.PT else Language.ES
    for name in RENDERER.names(language):
        for pick in range(RENDERER.variants(name, language)):
            reply = RENDERER.text(name, variant, pick=pick, **VALUES)
            assert "{" not in reply and "}" not in reply, name
            assert violations(reply, ALLOWED) == [], (name, reply)


def test_both_languages_have_the_same_templates():
    assert RENDERER.names(Language.ES) == RENDERER.names(Language.PT)


def test_register_follows_the_variant():
    assert RENDERER.text("ask_card", LanguageVariant.ES_MX) == "¿Tienes la tarjeta contigo?"
    assert RENDERER.text("ask_card", LanguageVariant.ES_CO) == "¿Tiene la tarjeta con usted?"
    assert RENDERER.text("ask_card", LanguageVariant.ES_AR) == "¿Tenés la tarjeta con vos?"
    assert RENDERER.text("ask_card", LanguageVariant.PT) == "O cartão está com você?"


def test_greeting_says_it_is_an_ai_and_offers_a_person():
    greeting = RENDERER.text("greeting", LanguageVariant.ES_CO, who=", Ana")
    assert greeting.startswith("Hola, Ana, soy VERA")
    assert "inteligencia artificial" in greeting and "persona" in greeting


def test_a_reply_that_comes_back_changes_its_words():
    for name in ("welcome", "out_of_scope_opening", "low_confidence", "rephrase"):
        for language, variant in ((Language.ES, LanguageVariant.ES_MX), (Language.PT, LanguageVariant.PT)):
            wordings = {RENDERER.text(name, variant, pick=pick) for pick in range(3)}
            assert RENDERER.variants(name, language) == 3 and len(wordings) == 3, (name, variant)


@pytest.mark.parametrize(
    ("amount", "currency", "text"),
    [
        (Decimal("120000"), Currency.COP, "COP 120.000"),
        (Decimal("87.50"), Currency.USD, "USD 87,50"),
        (Decimal("1600000.00"), Currency.ARS, "ARS 1.600.000"),
    ],
)
def test_money_keeps_the_currency_of_the_transaction_with_local_format(amount, currency, text):
    assert money(amount, currency) == text


def test_dates_are_written_in_words():
    assert day(date(2026, 7, 3), Language.ES) == "3 de julio de 2026"
    assert day(date(2026, 7, 3), Language.PT) == "3 de julho de 2026"


@pytest.mark.parametrize(
    ("reply", "rule"),
    [
        ("Ingresa a https://latam-bank.example para continuar", "link"),
        ("Visita www.banco.com", "link"),
        ("Para validar, dime el código OTP que te llegó", "secret_request"),
        ("Necesito el CVV de la tarjeta", "secret_request"),
        ("Me passa a sua senha?", "secret_request"),
        ("Tranquilo, te devolveremos el dinero mañana", "money_promise"),
        ("Garantizamos el reembolso", "money_promise"),
        ("Eso fue tu culpa por prestar la tarjeta", "blame"),
        ("Você autorizou essa compra", "blame"),
        ("Soy una persona real, no un robot", "human_claim"),
        ("Revisamos y no hubo suplantación", "impersonation_conclusion"),
        ("El cargo es de COP 999.999", "amount_not_from_tools"),
    ],
)
def test_forbidden_replies_are_blocked(reply: str, rule: str):
    assert rule in violations(reply, ALLOWED)
    with pytest.raises(UnsafeReplyError):
        check(reply, ALLOWED)


def test_amounts_from_tools_pass():
    assert check("Registré un reclamo por COP 185.000.", ALLOWED) == "Registré un reclamo por COP 185.000."
