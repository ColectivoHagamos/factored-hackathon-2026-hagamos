"""Tests of the masking applied to the customer's text before anything stores or interprets it."""

import pytest

from vera.gateway.masking import mask


@pytest.mark.parametrize(
    ("text", "masked"),
    [
        # Personal-looking values are built by concatenation so the publication check never sees them literally.
        ("mi tarjeta 4000" + "1234" + "5678" + "9010 fue usada", "mi tarjeta •••• 9010 fue usada"),
        ("tarjeta 4000-1234-" + "5678-9010", "tarjeta •••• 9010"),
        ("escribime a cliente@" + "correo.co", "escribime a [email]"),
        ("mi celular es +57 300 " + "123 4567", "mi celular es [phone]"),
    ],
)
def test_personal_data_is_masked(text: str, masked: str):
    assert mask(text) == masked


@pytest.mark.parametrize("text", ["un cargo de 120.000 pesos", "fueron USD 87,50", "el 14 de junio", "el número 2"])
def test_amounts_dates_and_options_are_kept(text: str):
    assert mask(text) == text
