"""A8 end to end (P27): «sí, pero quiero una persona» at the confirmation.

Expected: the person wins before any action; the pending registration is not executed and POL-01 is cited.
A8 needs no particular data; it uses the A5 customer, so the scenarios that share a customer stay few.
"""

from tests.e2e.conftest import CASE_ID, Customer


def test_a8_a_person_wins_over_the_pending_confirmation(client):
    customer = Customer(client, "A5")
    offer = customer.dispute(customer.pick_approved(customer.say(text="No reconozco un cargo de mi tarjeta")))
    assert offer["pending_confirmation"]["action"] == "register_dispute"

    human = customer.say(text="Sí, pero quiero hablar con una persona")
    assert "una persona" in human["reply"] and not CASE_ID.search(human["reply"])
    assert "POL-01" in {entry["rule_id"] for entry in human["glass_box"]}
    assert human["pending_confirmation"] is None and not human["options"]
