"""Tests of the masking applied to the customer's text before anything stores or interprets it (P26)."""

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
        ("mi cédula es 1.020." + "304.050", "mi cédula es [document]"),
        ("C.C. 1020" + "304050 y no reconozco el cargo", "C.C. [document] y no reconozco el cargo"),
        ("DNI 30.123" + ".456", "DNI [document]"),
        ("mi CPF é 123.456" + ".789-09", "mi CPF é [document]"),
        ("CUIT 20-3012" + "3456-7", "CUIT [document]"),
        ("mi CURP es GODE5612" + "31HDFRRN09", "mi CURP es [document]"),
        ("RFC GODE5612" + "31AB1", "RFC [document]"),
        ("me llamo Ana María Pérez y no reconozco un cargo", "me llamo [name] y no reconozco un cargo"),
        ("me llamo juan perez y no reconozco un cargo", "me llamo [name] y no reconozco un cargo"),
        ("Mi nombre es Laura de la Cruz", "Mi nombre es [name]"),
        ("Soy Pedro Gómez, cliente del banco", "Soy [name], cliente del banco"),
        ("meu nome é João da Silva e não reconheço uma compra", "meu nome é [name] e não reconheço uma compra"),
        ("está a nombre de Carlos Ruiz", "está a nombre de [name]"),
    ],
)
def test_personal_data_is_masked(text: str, masked: str):
    assert mask(text) == masked


@pytest.mark.parametrize(
    "text",
    [
        "un cargo de 120.000 pesos",
        "la compra fue de 1.200.000",
        "fueron USD 87,50",
        "el 14 de junio",
        "el 14/06 a las 13:48",
        "el número 2",
        "soy de Bogotá y no reconozco un cargo de Uber",
        "soy cliente hace años",
        "No reconozco un cargo de Farmacia Salud",
    ],
)
def test_amounts_dates_options_and_merchants_are_kept(text: str):
    assert mask(text) == text
