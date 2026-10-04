"""A2 end to end (P30): a pending charge is clarified before anything is disputed.

Expected: VERA explains that the charge is still pending, without judging, and opens nothing if the customer now
recognizes it (POL-04). If not, the pending charge counts as a signal: the card block is offered with confirmation
and the Fraud team is alerted (POL-06, POL-16), but a pending charge alone is never disputed.
"""

from tests.e2e.conftest import CASE_ID, Customer


def test_a2_a_pending_charge_is_explained_and_nothing_is_opened(client):
    customer = Customer(client, "A2")
    listed = customer.say(text="No reconozco un cargo de mi tarjeta")
    receipt = customer.choose(listed, "pendiente")
    assert "Estado: pendiente" in receipt["reply"] and "todavía está pendiente" in receipt["reply"]
    assert "POL-04" in customer.rules()

    done = customer.say(selected_option="yes")
    assert not CASE_ID.search(done["reply"]) and not done["options"] and done["pending_confirmation"] is None


def test_a2_a_pending_charge_not_recognized_is_a_signal_not_a_dispute(client):
    customer = Customer(client, "A2")
    receipt = customer.choose(customer.say(text="No reconozco un cargo de mi tarjeta"), "pendiente")
    last = customer.dispute(receipt, block="no")

    assert customer.offered("block_card") and {"POL-06", "POL-16"} <= customer.rules()
    assert not customer.offered("register_dispute") and not CASE_ID.search(last["reply"])
