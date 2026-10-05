"""A purchase charged twice: VERA finds the purchases of that merchant, asks which one is repeated, never asks fraud
questions, and registers a duplicate for Complaints."""

import pytest
from fastapi.testclient import TestClient

from api.dependencies import build
from api.main import create_app
from api.settings import Settings
from tests.contract.test_api import CO_02, Clock, login, say
from vera.contracts.handoff import Handoff

OPENINGS = {
    "es": ("Me cobraron dos veces la misma compra en Uber", "cobro repetido"),
    "pt": ("Fui cobrado duas vezes pela mesma compra no Uber", "cobrança repetida"),
}


@pytest.mark.parametrize("llm", ["rules", "classifier"])
@pytest.mark.parametrize("language", ["es", "pt"])
def test_a_duplicate_is_registered_for_complaints_without_fraud_questions(llm: str, language: str):
    settings = Settings(session_secret="test-secret", messages_per_minute=50, llm=llm)
    client = TestClient(create_app(settings, build(settings, now=Clock())))
    headers = login(client, CO_02)
    conversation = client.post("/v1/conversations", json={"preferred_language": language}, headers=headers).json()
    opening, words = OPENINGS[language]

    listed = say(client, headers, conversation["conversation_id"], text=opening)
    assert words in listed.reply
    # Both purchases of that merchant are offered; VERA never picks the repeated one by itself.
    assert len(listed.options) == 2 and all("Uber" in option.label for option in listed.options)

    replies = [listed]
    for body in ({"selected_option": listed.options[0].n}, {"selected_option": "yes"}, {"selected_option": "yes"}):
        replies.append(say(client, headers, conversation["conversation_id"], **body))
    done = replies[-1]
    assert done.case_id
    assert not any("tarjeta con" in reply.reply or "cartão está com" in reply.reply for reply in replies)

    analyst = {"Authorization": f"Bearer {client.post('/v1/demo-analyst-session').json()['token']}"}
    handoff = Handoff.model_validate(client.get(f"/v1/cases/{done.case_id}/handoff", headers=analyst).json())
    assert (handoff.reason, handoff.suggested_queue, handoff.claim_type) == (
        "duplicate",
        "complaints",
        "improper_charge",
    )
