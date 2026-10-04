"""Masking of the customer's text before the interpreter, the logs or the event log see it."""

import re

PATTERNS = (
    # Card numbers, with or without separators: only the last four digits survive. A leading "+" marks a phone.
    (re.compile(r"(?<![+\d])\b(?:\d[ -]?){8,15}(\d{4})\b"), r"•••• \1"),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[email]"),
    (re.compile(r"\+?\d{1,3}[ -]?\(?\d{2,3}\)?[ -]?\d{3,4}[ -]?\d{4}\b"), "[phone]"),
)


def mask(text: str) -> str:
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text
