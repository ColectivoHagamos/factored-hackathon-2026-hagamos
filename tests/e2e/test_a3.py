"""A3 end to end (P31): mitigation when the customer does not have the card.

Expected: the sweep shows the other charges of the card; the block is confirmed and read back; one case groups the
charges with their total; the handoff goes to the Fraud queue with the actions and a network reason code.
"""

from tests.e2e.conftest import APPROVED, CASE_ID, Customer, analyst_view


def test_a3_the_block_is_confirmed_and_one_case_goes_to_fraud(client):
    customer = Customer(client, "A3")
    listed = customer.say(text="No reconozco un cargo de mi tarjeta")
    # The oldest approved charge, so the sweep covers the later ones of the same card.
    receipt = customer.choose(listed, APPROVED[0], last=True)
    offer = customer.dispute(receipt, has_card=False, swept="no reconozco ninguno", block="yes")

    assert customer.offered("block_card")
    assert any("bloqueada" in reply["reply"] for reply in customer.replies)
    assert offer["pending_confirmation"]["action"] == "register_dispute"
    case_id = CASE_ID.search(customer.say(selected_option="yes")["reply"]).group(0)

    handoff = analyst_view(client, case_id)
    assert handoff["suggested_queue"] == "fraud" and handoff["fraud_alert"]
    assert {action["action"] for action in handoff["actions"]} >= {"block_card", "register_dispute"}
    assert handoff["network_clock"]["suggested_code"] in ("10.4", "10.3")
