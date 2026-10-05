"""A9 end to end (P29): an ambiguous claim and a question on the side.

Expected: with two charges of the same merchant VERA lists both and asks which, never choosing; a balance question
is answered as out of scope and the same options stay open; the chosen charge is the one clarified.
The merchant comes from the first listing, so the test holds for the mock and for the demo subset.
"""

from tests.e2e.conftest import Customer


def merchant_of(label: str) -> str:
    """Merchant of an option label such as «14 de junio de 2026, 13:48: Uber, Bogota, COP 65.000. ...»."""
    return label.split(": ", 1)[1].split(",")[0]


def test_a9_the_customer_chooses_and_a_side_question_does_not_cut_the_flow(client):
    opener = Customer(client, "A9")
    first = opener.say(text="No reconozco un cargo de mi tarjeta")
    merchants = [merchant_of(option["label"]) for option in first["options"]]
    repeated = next(merchant for merchant in merchants if merchants.count(merchant) > 1)

    customer = Customer(client, "A9", ref=opener.ref)
    listed = customer.say(text=f"No reconozco el cargo de {repeated}")
    same = [option for option in listed["options"] if merchant_of(option["label"]) == repeated]
    assert len(same) >= 2 and not any(option.get("answer") for option in listed["options"])
    assert any(entry["rule_id"] == "POL-05" for entry in listed["glass_box"])

    aside = customer.say(text="¿Y mi saldo?")
    assert "banca en línea" in aside["reply"] and aside["options"] == listed["options"]

    chosen = customer.say(selected_option=same[1]["n"])
    # The chosen charge, and nothing else, is shown and asked about (the wording follows the country).
    assert same[1]["label"] in chosen["reply"] and same[0]["label"] not in chosen["reply"]
    assert [option["answer"] for option in chosen["options"]] == ["yes", "no"]
