"""A payment made under deception, end to end (POL-10): key questions, an answer, and Fraud gets both.

Expected: VERA asks when the transfer was made and how the customer was contacted, waits for the answer, says that a
transfer has no chargeback, and passes the case to Fraud with what the customer said. No case and no action.
"""

from tests.e2e.conftest import CASE_ID, Customer, analyst_get


def test_a_scam_gets_its_key_questions_and_goes_to_fraud_with_the_answers(client):
    customer = Customer(client, "A5")
    asked = customer.say(text="Transferí plata a una cuenta que me dieron por teléfono y era una estafa")
    assert "¿cuándo fue la transferencia" in asked["reply"] and "POL-10" in customer.rules()
    answered = customer.say(text="Fue ayer por la tarde")
    assert "contracargo" in answered["reply"] and not CASE_ID.search(answered["reply"])

    trace = f"trace-{customer.conversation}"
    item = next(item for item in analyst_get(client, "/v1/queue") if item["trace_id"] == trace)
    note = analyst_get(client, f"/v1/transfers/{item['reference']}")
    assert (note["reason"], note["suggested_queue"]) == ("scam_transfer", "fraud")
    declared = note["declared_by_customer"]
    assert (declared["authorized_payment"], declared["contacted_by"]) == ("yes", "phone_call")
    # The customer's own words: the rules keep "ayer", a language model may keep "ayer por la tarde".
    assert declared["date_text"].startswith("ayer")
