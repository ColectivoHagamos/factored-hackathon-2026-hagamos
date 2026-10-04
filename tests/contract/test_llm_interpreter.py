"""The language model behind the API (P41): only masked text reaches it, and what it costs shows in the metrics."""

from fastapi.testclient import TestClient

import api.dependencies
from api.dependencies import build
from api.main import create_app
from api.settings import Settings
from tests.llm_fake import READ, FakeMessages, reply
from vera.adapters.mock_bank import CLOCK
from vera.llm.anthropic_adapter import AnthropicInterpreter

CO_01 = "CUS-MOCK00000000001"


def test_only_masked_text_reaches_the_model_and_its_usage_shows_in_the_metrics(monkeypatch):
    messages = FakeMessages(reply(READ))
    monkeypatch.setattr(api.dependencies, "interpreter_for", lambda settings: (AnthropicInterpreter(messages), False))
    settings = Settings(session_secret="test-secret", llm="anthropic")
    client = TestClient(create_app(settings, build(settings, now=lambda: CLOCK)))
    token = client.post("/v1/demo-session", json={"demo_customer": CO_01}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    conversation = client.post("/v1/conversations", json={}, headers=headers).json()["conversation_id"]
    text = "No reconozco 185.000 de Libreria Andina en mi tarjeta 4000123456789010, me llamo Ana Pérez"
    sent = client.post(f"/v1/conversations/{conversation}/messages", json={"text": text}, headers=headers)
    assert sent.status_code == 200
    content = messages.requests[0]["messages"][0]["content"]
    assert "4000123456789010" not in content and "•••• 9010" in content and "Ana Pérez" not in content
    analyst = client.post("/v1/demo-analyst-session").json()["token"]
    metrics = client.get("/v1/metrics", headers={"Authorization": f"Bearer {analyst}"}).json()
    assert metrics["interpreter"] == "anthropic" and metrics["llm"]["calls"] == 1
    assert metrics["llm"]["spent_usd"] == 0.0025 and metrics["llm"]["cap_usd"] == 15.0
    assert client.get("/v1/health").json()["llm_provider"] == "anthropic"
