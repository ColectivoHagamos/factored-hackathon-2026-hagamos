"""A6 end to end (P34): a Colombian customer writes in Portuguese about a charge in São Paulo.

Expected: every reply in Portuguese; the dated term is only the one with an official text (Ley 1755), never the
Decreto 587, which does not apply to a merchant abroad; the analyst gets a Portuguese-speaking flag and the card
network reason code.
"""

from tests.e2e.conftest import CASE_ID, Customer, analyst_view


def test_a6_portuguese_from_start_to_handoff_for_a_charge_in_sao_paulo(client):
    customer = Customer(client, "A6")
    assert customer.country == "CO"
    receipt = customer.choose(customer.say(text="Não reconheço uma cobrança em São Paulo"), "São Paulo")
    assert "Situação" in receipt["reply"] and "São Paulo" in receipt["reply"]

    offer = customer.dispute(receipt, has_card=False, block="no")
    assert offer["pending_confirmation"]["action"] == "register_dispute" and "Você confirma" in offer["reply"]
    done = customer.say(selected_option="yes")

    case_id = CASE_ID.search(done["reply"]).group(0)
    assert "reclamação" in done["reply"] and "587" not in done["reply"]
    handoff = analyst_view(client, case_id)
    assert handoff["requires_pt_analyst"] and handoff["network_clock"]["suggested_code"] == "10.4"
