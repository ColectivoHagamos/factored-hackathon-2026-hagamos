"""A4 end to end (P32): a Mexican customer disputes a charge made in Madrid.

Expected: the charge is found by the place the customer names, even beyond the recent window; the case is
registered; the route of the clarification (LTOSF, art. 23) is recorded without a date, because no N1 text is
loaded for it, and VERA invents none.
"""

from tests.e2e.conftest import CASE_ID, Customer


def test_a4_a_charge_in_madrid_gets_its_route_without_an_invented_date(client):
    customer = Customer(client, "A4")
    assert customer.country == "MX"
    receipt = customer.choose(customer.say(text="No reconozco un cargo en Madrid"), "Madrid")
    assert "Madrid" in receipt["reply"]

    offer = customer.dispute(receipt)
    assert offer["pending_confirmation"]["action"] == "register_dispute"
    done = customer.say(selected_option="yes")

    assert CASE_ID.search(done["reply"]) and "LTOSF, art. 23" in done["reply"]
    assert "a más tardar" not in done["reply"] and not any(entry.get("deadline") for entry in done["glass_box"])
