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


@pytest.fixture(scope="module")
def client() -> Iterator:
    url = os.environ.get("VERA_E2E_URL")
    if url:
        with httpx2.Client(base_url=url, timeout=30) as remote:
            yield remote
        return
    settings = Settings(session_secret="e2e-secret", messages_per_minute=200)
    yield TestClient(create_app(settings, build(settings, now=lambda: CLOCK)))


class Customer:
    """A demo customer driving one conversation over HTTP."""

    def __init__(self, client, scenario: str) -> None:
        demo = client.get("/v1/demo-customers")
        assert demo.status_code == 200
        chosen = next(c for c in demo.json() if any(tag.split("_")[0] == scenario for tag in c["scenarios"]))
        token = client.post("/v1/demo-session", json={"demo_customer": chosen["customer_ref"]}).json()["token"]
        self.client = client
        self.country = chosen["country"]
        self.headers = {"Authorization": f"Bearer {token}"}
        started = client.post("/v1/conversations", json={}, headers=self.headers).json()
        self.conversation = started["conversation_id"]
        self.greeting = started["greeting"]

    def say(self, **body) -> dict:
        response = self.client.post(f"/v1/conversations/{self.conversation}/messages", json=body, headers=self.headers)
        assert response.status_code == 200, response.text
        return response.json()

    @staticmethod
    def approved_option(reply: dict) -> int:
        return next(o["n"] for o in reply["options"] if "aprobado" in o["label"] or "aprovada" in o["label"])


def now() -> datetime:
    return CLOCK
