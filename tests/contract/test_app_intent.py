"""The bank's app sends the button the customer pressed with the text that names the charge: the button is the claim,
the text is the charge, and a person or a threat in the text still wins."""

import pytest
from fastapi.testclient import TestClient

from api.dependencies import build
from api.main import create_app
from api.settings import Settings
from tests.contract.test_api import Clock, login, say

TERSE = "Libreria Andina, COP 185.000"


@pytest.fixture
def client() -> TestClient:
    settings = Settings(session_secret="test-secret", messages_per_minute=50)
    return TestClient(create_app(settings, build(settings, now=Clock())))


def open_conversation(client: TestClient, language: str = "es") -> tuple[dict, str]:
    headers = login(client)
    started = client.post("/v1/conversations", json={"preferred_language": language}, headers=headers).json()
    return headers, started["conversation_id"]


def test_without_the_button_a_terse_text_leaves_the_claim_open(client):
    headers, conversation = open_conversation(client)
    reply = say(client, headers, conversation, text=TERSE)
    assert reply.charge is None


@pytest.mark.parametrize("language", ["es", "pt"])
def test_the_button_is_the_claim_and_the_text_names_the_charge(client, language):
    headers, conversation = open_conversation(client, language)
    reply = say(client, headers, conversation, text=TERSE, intent="unrecognized_charge")
    assert reply.stage == "analysis" and reply.charge and reply.charge.merchant == "Libreria Andina"


def test_a_person_asked_for_in_the_text_wins_over_the_button(client):
    headers, conversation = open_conversation(client)
    reply = say(client, headers, conversation, text="Quiero hablar con una persona", intent="unrecognized_charge")
    assert reply.charge is None and "analista" in reply.reply.lower()


def test_an_intent_needs_the_text_that_names_the_charge(client):
    headers, conversation = open_conversation(client)
    response = client.post(
        f"/v1/conversations/{conversation}/messages",
        json={"selected_option": "yes", "intent": "unrecognized_charge"},
        headers=headers,
    )
    assert response.status_code == 422
