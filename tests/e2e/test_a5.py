"""A5 end to end (P32): an Argentine customer disputes a credit card purchase.

Expected: the dispute follows Ley 25.065 with its dated deadlines (acknowledge, then correct or explain), and the
BCRA term for the complaint; the block is offered only at the customer's request, so nothing is blocked here.
"""

from tests.e2e.conftest import CASE_ID, Customer


def test_a5_a_credit_card_dispute_in_argentina_gets_the_ley_25065_deadlines(client):
    customer = Customer(client, "A5")
    assert customer.country == "AR"
    receipt = customer.pick_approved(customer.say(text="No reconozco un cargo de mi tarjeta"))

    offer = customer.dispute(receipt)
    assert offer["pending_confirmation"]["action"] == "register_dispute"
    done = customer.say(selected_option="yes")

    assert CASE_ID.search(done["reply"]) and "Ley 25.065, art. 27" in done["reply"]
    dated = {entry["rule_id"] for entry in done["glass_box"] if entry.get("deadline")}
    assert {"AR-R05", "AR-R03"} <= dated
    assert not customer.offered("block_card")
