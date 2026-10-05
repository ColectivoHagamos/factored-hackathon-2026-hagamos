"""End-to-end tests talk only HTTP. With VERA_E2E_URL they run against a deployment; otherwise against the
application in memory with the mock adapter, at the simulated clock of the mock data."""

import os
import re
from collections.abc import Iterator
from datetime import datetime

import httpx2
import pytest
from fastapi.testclient import TestClient

from api.dependencies import build
from api.main import create_app
from api.settings import Settings
from vera.adapters.mock_bank import CLOCK

CASE_ID = re.compile(r"DSP-\d{6}")
# The card question in every variant: "¿Tiene la tarjeta con usted?", "O cartão está com você?".
CARD_QUESTION = re.compile(r"tarjeta con|cartão está com")
APPROVED = ("aprobado", "aprovada")


@pytest.fixture(scope="module", params=["rules", "classifier"])
def client(request) -> Iterator:
    """In memory, every scenario runs with both interpreters; against a URL, with the one deployed."""
    url = os.environ.get("VERA_E2E_URL")
    if url:
        if request.param != "rules":
            pytest.skip("a deployment runs the interpreter it was configured with")
        with httpx2.Client(base_url=url, timeout=30) as remote:
            yield remote
        return
    settings = Settings(session_secret="e2e-secret", messages_per_minute=200, llm=request.param)
    yield TestClient(create_app(settings, build(settings, now=lambda: CLOCK)))


def access(client) -> dict:
    """The login of the jury and the team; VERA_E2E_LOGIN ("user:password") opens a deployment that requires it."""
    login = os.environ.get("VERA_E2E_LOGIN")
    if not login:
        return {}
    username, password = login.split(":", 1)
    response = client.post("/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


class Customer:
    """A demo customer driving one conversation over HTTP."""

    def __init__(self, client, scenario: str) -> None:
        entry = access(client)
        demo = client.get("/v1/demo-customers", headers=entry)
        assert demo.status_code == 200
        chosen = next(c for c in demo.json() if any(tag.split("_")[0] == scenario for tag in c["scenarios"]))
        session = client.post("/v1/demo-session", json={"demo_customer": chosen["customer_ref"]}, headers=entry)
        token = session.json()["token"]
        self.client = client
        self.ref = chosen["customer_ref"]
        self.country = chosen["country"]
        self.headers = {"Authorization": f"Bearer {token}"}
        started = client.post("/v1/conversations", json={}, headers=self.headers).json()
        self.conversation = started["conversation_id"]
        self.greeting = started["greeting"]
        self.replies: list[dict] = []

    def say(self, **body) -> dict:
        response = self.client.post(f"/v1/conversations/{self.conversation}/messages", json=body, headers=self.headers)
        assert response.status_code == 200, response.text
        self.replies.append(response.json())
        return self.replies[-1]

    def rules(self) -> set[str]:
        """Every rule cited in the glass box during the conversation."""
        return {entry["rule_id"] for reply in self.replies for entry in reply["glass_box"]}

    def offered(self, action: str) -> bool:
        return any((reply.get("pending_confirmation") or {}).get("action") == action for reply in self.replies)

    @staticmethod
    def approved_option(reply: dict) -> int:
        return next(o["n"] for o in reply["options"] if any(word in o["label"] for word in APPROVED))

    def choose(self, reply: dict, *words: str, last: bool = False) -> dict:
        """With several candidates, chooses one whose label has all the words (the oldest with last=True)."""
        if not reply["options"] or any(o.get("answer") for o in reply["options"]):
            return reply
        matching = [o for o in reply["options"] if all(word in o["label"] for word in words)]
        return self.say(selected_option=matching[-1 if last else 0]["n"])

    def pick_approved(self, reply: dict) -> dict:
        """With several candidates, chooses an approved one; a single candidate is already shown."""
        if reply["options"] and not any(o.get("answer") for o in reply["options"]):
            return self.say(selected_option=self.approved_option(reply))
        return reply

    def dispute(self, reply: dict, *, has_card: bool = True, swept: str = "todos", block: str = "no") -> dict:
        """From «¿Reconoce el cargo?»: not recognized and bought online, then the card, the sweep and the block as
        given. Returns the reply that asks to confirm the registration, or the last one when none does."""
        reply = self.say(selected_option="no")
        for _ in range(6):
            pending = (reply.get("pending_confirmation") or {}).get("action")
            if pending == "register_dispute" or not reply["options"]:
                break
            if pending == "block_card":
                reply = self.say(selected_option=block)
            elif reply.get("multiple_choice"):
                reply = self.say(text=swept)
            elif CARD_QUESTION.search(reply["reply"]):
                reply = self.say(selected_option="yes" if has_card else "no")
            else:
                reply = self.say(selected_option="yes")
        return reply

    def deny_until_registration(self, reply: dict) -> dict:
        """From «¿Reconoce el cargo?»: not recognized, bought online, card at hand, every swept charge, no block."""
        return self.dispute(reply)


def analyst_get(client, path: str):
    """What the analyst console reads; VERA_E2E_ANALYST_KEY opens a closed deployment."""
    key = os.environ.get("VERA_E2E_ANALYST_KEY")
    headers = {**access(client), **({"X-Analyst-Key": key} if key else {})}
    session = client.post("/v1/demo-analyst-session", headers=headers)
    assert session.status_code == 200, session.text
    response = client.get(path, headers={"Authorization": f"Bearer {session.json()['token']}"})
    assert response.status_code == 200, response.text
    return response.json()


def analyst_view(client, case_id: str) -> dict:
    """The handoff of a case as the analyst console reads it."""
    return analyst_get(client, f"/v1/cases/{case_id}/handoff")


def now() -> datetime:
    return CLOCK
