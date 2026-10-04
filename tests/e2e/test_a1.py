"""A1 end to end (P22): a Colombian customer disputes a recent purchase without signals.

Expected: the charge is found and clarified, one case is registered and read back, and the bank complaint
deadline (CO-R15, Ley 1755) is dated in the reply and cited with its source in the glass box.
"""

from tests.e2e.conftest import CASE_ID, Customer


def test_a1_dispute_of_a_recent_purchase_in_colombia(client):
    customer = Customer(client, "A1")
    assert customer.country == "CO"
    assert "inteligencia artificial" in customer.greeting

    reply = customer.say(text="No reconozco un cargo de mi tarjeta")
    if reply["options"] and not any(o.get("answer") for o in reply["options"]):
        reply = customer.say(selected_option=Customer.approved_option(reply))
    assert "¿Reconoce el cargo" in reply["reply"]

    reply = customer.say(selected_option="no")
    if "internet" in reply["reply"]:
        reply = customer.say(selected_option="yes")
    if "tarjeta con usted" in reply["reply"]:
        reply = customer.say(selected_option="yes")
    if reply.get("multiple_choice"):
        reply = customer.say(text="todos")
    if reply.get("pending_confirmation", {}) and reply["pending_confirmation"]["action"] == "block_card":
        reply = customer.say(selected_option="no")

    assert reply["pending_confirmation"]["action"] == "register_dispute"
    done = customer.say(selected_option="yes")

    case_id = CASE_ID.search(done["reply"]).group(0)
    assert "a más tardar" in done["reply"]
    assert any(entry["rule_id"] == "CO-R15" and entry["deadline"] for entry in done["glass_box"])
    view = client.get(f"/v1/cases/{case_id}", headers=customer.headers)
    assert view.status_code == 200 and view.json()["case"]["case_id"] == case_id
