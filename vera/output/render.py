"""Customer replies from templates, with the register of each variant and local formats for money and dates."""

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml

from vera.contracts.charges import ChargeStatus
from vera.contracts.common import Currency, Language
from vera.contracts.handoff import LanguageVariant

TEMPLATES = Path(__file__).with_name("templates")
MONTHS = {
    Language.ES: (
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ),
    Language.PT: (
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    ),
}
STATUS_WORDS = {
    Language.ES: {"approved": "aprobado", "pending": "pendiente", "declined": "rechazado", "reversed": "revertido"},
    Language.PT: {"approved": "aprovada", "pending": "pendente", "declined": "recusada", "reversed": "estornada"},
}


def language_of(variant: LanguageVariant) -> Language:
    return Language.PT if variant is LanguageVariant.PT else Language.ES


def money(amount: Decimal, currency: Currency) -> str:
    """Amount in the currency of the transaction, as written in the region: COP 120.000 or USD 87,50."""
    whole, cents = f"{amount:.2f}".split(".")
    grouped = f"{int(whole):,}".replace(",", ".")
    return f"{currency.value} {grouped}" if cents == "00" else f"{currency.value} {grouped},{cents}"


def day(value: date, language: Language) -> str:
    return f"{value.day} de {MONTHS[language][value.month - 1]} de {value.year}"


def status_word(status: ChargeStatus, language: Language) -> str:
    return STATUS_WORDS[language][status.value]


class Renderer:
    def __init__(self, folder: Path = TEMPLATES) -> None:
        self._templates: dict[Language, dict[str, str]] = {}
        self._register: dict[Language, dict[str, dict[str, str]]] = {}
        for language in Language:
            content = yaml.safe_load((folder / f"{language.value}.yaml").read_text(encoding="utf-8"))
            self._templates[language] = content["templates"]
            self._register[language] = content.get("register") or {}

    def names(self, language: Language) -> frozenset[str]:
        return frozenset(self._templates[language])

    def text(self, name: str, variant: LanguageVariant, **values: object) -> str:
        language = language_of(variant)
        words = self._register[language].get(variant.value) or {}

        def fill(match: re.Match) -> str:
            key = match.group(1)
            if key in values:
                return str(values[key])
            word = words.get(key[0].lower() + key[1:])
            if word is None:
                raise KeyError(f"template {name} needs a value for {key}")
            return word[0].upper() + word[1:] if key[0].isupper() else word

        return re.sub(r"\{(\w+)\}", fill, self._templates[language][name])
