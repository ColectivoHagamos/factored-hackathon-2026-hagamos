"""A1 end to end (P22): a Colombian customer disputes a recent purchase without signals.

Expected: the charge is found and clarified, one case is registered and read back, and the bank complaint
deadline (CO-R15, Ley 1755) is dated in the reply and cited with its source in the glass box.
"""

from tests.e2e.conftest import CASE_ID, Customer


def test_a1_dispute_of_a_recent_purchase_in_colombia(client):
    customer = Customer(client, "A1")
    assert customer.country == "CO"
    assert "inteligencia artificial" in customer.greeting

    reply = customer.pick_approved(customer.say(text="No reconozco un cargo de mi tarjeta"))
    assert "¿Reconoce el cargo" in reply["reply"]

    reply = customer.deny_until_registration(reply)
    assert reply["pending_confirmation"]["action"] == "register_dispute"
    done = customer.say(selected_option="yes")

    case_id = CASE_ID.search(done["reply"]).group(0)
    assert "a más tardar" in done["reply"]
    assert any(entry["rule_id"] == "CO-R15" and entry["deadline"] for entry in done["glass_box"])
    view = client.get(f"/v1/cases/{case_id}", headers=customer.headers)
    assert view.status_code == 200 and view.json()["case"]["case_id"] == case_id
