"""A10 end to end (P35): «me cobraron un ajuste que no corresponde».

Expected: the bank adjustment is identified from the records (verified), the reason is the customer's (declared),
one case is registered and the handoff goes to Complaints, which decides; VERA decides nothing about the money, and
a goodwill flag, if any, is never shown to the customer (POL-17).
"""

from tests.e2e.conftest import CASE_ID, Customer, analyst_view


def test_a10_an_improper_bank_charge_is_identified_registered_and_sent_to_complaints(client):
    customer = Customer(client, "A10")
    receipt = customer.choose(customer.say(text="Me cobraron un ajuste que no corresponde"), "Ajuste")
    assert "Ajuste del banco" in receipt["reply"] and "POL-11" in customer.rules()

    confirm = customer.say(selected_option="yes")
    assert confirm["pending_confirmation"]["action"] == "register_dispute"
    done = customer.say(selected_option="yes")

    case_id = CASE_ID.search(done["reply"]).group(0)
    handoff = analyst_view(client, case_id)
    assert handoff["suggested_queue"] == "complaints" and handoff["claim_type"] == "improper_charge"
    assert "POL-17" not in customer.rules()
