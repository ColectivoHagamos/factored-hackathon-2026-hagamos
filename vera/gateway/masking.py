"""Masking of the customer's text before the interpreter, the logs or the event log see it.

A document or a name is masked where its shape or the words around it say what it is. A bare number is left alone,
because amounts are written the same way ("1.200.000"), and the flow needs them.
"""

import re

NAME_WORD = r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+"
# Words that end a name typed in lower case: "me llamo juan y no reconozco...".
NOT_A_NAME = r"(?:y|e|o|no|nao|pero|mas|porque|que|tengo|quiero|tenho|quero|con|com|en|em|a|al|el|la|un|una|um|uma)"
# Particles inside a surname: "de la Cruz", "da Silva".
PARTICLE = r"(?:de las|de los|de la|del|de|das|dos|da|do)"

PATTERNS = (
    # Card numbers, with or without separators: only the last four digits survive. A leading "+" marks a phone.
    (re.compile(r"(?<![+\d])\b(?:\d[ -]?){8,15}(\d{4})\b"), r"•••• \1"),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[email]"),
    # Documents with a shape of their own: CURP and RFC (MX), CUIT or CUIL (AR), CPF (BR).
    (re.compile(r"\b[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d\b"), "[document]"),
    (re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b"), "[document]"),
    (re.compile(r"\b\d{2}-\d{8}-\d\b"), "[document]"),
    (re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), "[document]"),
    # Any other number right after a document word: cédula, C.C., DNI, CPF, RG...
    (
        re.compile(
            r"(?i)\b(c[eé]dula|c\.c\.|cc|dni|documento|identificaci[oó]n|pasaporte|cpf|rg|cuit|cuil|curp|rfc)(?!\w)"
            r"(\s*(?:es|de|n[uú]mero|nro\.?|no\.?|n°|#|:)?\s*)\d[\d.\-]{4,18}\d"
        ),
        r"\1\2[document]",
    ),
    (re.compile(r"\+?\d{1,3}[ -]?\(?\d{2,3}\)?[ -]?\d{3,4}[ -]?\d{4}\b"), "[phone]"),
    # A name where the customer introduces it; after "soy" or "sou" only a capitalized one.
    (
        re.compile(
            rf"\b((?i:me llamo|mi nombre es|a nombre de|meu nome [eé]|me chamo)\s+)"
            rf"(?!(?i:{NOT_A_NAME})\b)[^\W\d_]+(?:\s+(?:(?i:{PARTICLE})\s+)?(?!(?i:{NOT_A_NAME})\b)[^\W\d_]+){{0,3}}"
        ),
        r"\1[name]",
    ),
    (re.compile(rf"\b((?i:soy|sou)\s+){NAME_WORD}(?:\s+(?:{PARTICLE}\s+)?{NAME_WORD}){{0,3}}"), r"\1[name]"),
)


def mask(text: str) -> str:
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text
