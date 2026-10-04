"""A8 end to end (P27): «sí, pero quiero una persona» at the confirmation.

Expected (policy v1.5, POL-01): one offer to review the case first, and no action runs meanwhile; a customer who
insists gets a person, the pending registration is never executed, and the analyst gets what is already known.
A8 needs no particular data; it uses the A5 customer, so the scenarios that share a customer stay few.
"""

from tests.e2e.conftest import CASE_ID, Customer, analyst_get


def test_a8_a_person_wins_over_the_pending_confirmation(client):
    customer = Customer(client, "A5")
    offer = customer.dispute(customer.pick_approved(customer.say(text="No reconozco un cargo de mi tarjeta")))
    assert offer["pending_confirmation"]["action"] == "register_dispute"

    human = customer.say(text="Sí, pero quiero hablar con una persona")
    assert "analista" in human["reply"] and not CASE_ID.search(human["reply"])
    assert "POL-01" in {entry["rule_id"] for entry in human["glass_box"]}
    assert human["pending_confirmation"] is None and [o["answer"] for o in human["options"]] == ["yes", "no"]

    insisted = customer.say(text="No, quiero hablar con una persona")
    assert "una persona" in insisted["reply"] and not CASE_ID.search(insisted["reply"])
    assert insisted["pending_confirmation"] is None and not insisted["options"]

    trace = f"trace-{customer.conversation}"
    item = next(item for item in analyst_get(client, "/v1/queue") if item["trace_id"] == trace)
    note = analyst_get(client, f"/v1/transfers/{item['reference']}")
    assert note["reason"] == "person_requested" and note["pending_action_not_run"] == "register_dispute"
    assert note["charges"] and note["case_id"] is None
