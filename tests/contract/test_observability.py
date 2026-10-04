"""Operations (P54): one JSON line per request and per turn, a trace per conversation, metrics and the fallback."""

import json
import logging

import pytest
from fastapi.testclient import TestClient

import ml.claims
from api.dependencies import build
from api.main import create_app
from api.settings import Settings
from vera.adapters.mock_bank import CLOCK

CO_01 = "CUS-MOCK00000000001"


class Lines(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(json.loads(record.getMessage()))


@pytest.fixture
def lines():
    handler = Lines()
    logger = logging.getLogger("vera.operations")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    yield handler.records
    logger.removeHandler(handler)


@pytest.fixture
def client() -> TestClient:
    settings = Settings(session_secret="test-secret", messages_per_minute=50)
    return TestClient(create_app(settings, build(settings, now=lambda: CLOCK)))


def converse(client: TestClient, text: str) -> tuple[dict, str]:
    token = client.post("/v1/demo-session", json={"demo_customer": CO_01}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    conversation = client.post("/v1/conversations", json={}, headers=headers).json()["conversation_id"]
    client.post(f"/v1/conversations/{conversation}/messages", json={"text": text}, headers=headers)
    return headers, conversation


def test_every_request_gets_an_id_back_and_one_line_without_ids_in_the_route(client, lines):
    echoed = client.get("/v1/health", headers={"X-Request-ID": "trace-12345678"})
    replaced = client.get("/v1/health", headers={"X-Request-ID": "not a valid id!"})
    assert echoed.headers["X-Request-ID"] == "trace-12345678"
    assert len(replaced.headers["X-Request-ID"]) == 32
    request = next(r for r in lines if r["event"] == "request" and r["request_id"] == "trace-12345678")
    assert request["route"] == "/v1/health" and request["status"] == 200 and request["ms"] >= 0


def test_a_turn_is_traced_by_its_conversation_and_never_logs_what_the_customer_wrote(client, lines):
    _, conversation = converse(client, "No reconozco un cargo de Libreria Andina, mi tarjeta 4000123456789010")
    turn = next(r for r in lines if r["event"] == "turn")
    assert turn["trace_id"] == f"trace-{conversation}" and turn["tools"][0].startswith("search_charges:")
    routes = {r["route"] for r in lines if r["event"] == "request"}
    assert "/v1/conversations/{conversation_id}/messages" in routes
    everything = json.dumps(lines, ensure_ascii=False)
    assert "Libreria" not in everything and "9010" not in everything and CO_01 not in everything


def test_metrics_are_for_the_analyst_role_only(client):
    headers, _ = converse(client, "No reconozco un cargo de Libreria Andina")
    assert client.get("/v1/metrics", headers=headers).status_code == 401
    analyst = client.post("/v1/demo-analyst-session").json()["token"]
    metrics = client.get("/v1/metrics", headers={"Authorization": f"Bearer {analyst}"}).json()
    assert metrics["counts"]["turns"] == 1 and metrics["interpreter"] == "rules" and not metrics["degraded"]
    assert metrics["turn_ms"]["n"] == 1


def test_metrics_measure_who_asks_for_a_person_who_takes_the_offer_and_how_they_end(client, lines):
    """POL-01, policy section 16: the evidence Compliance needs to adjust the number of offers."""
    for answers in (["sí", "No reconozco un cargo de Libreria Andina", "sí"], ["no"]):
        headers, conversation = converse(client, "Quiero hablar con una persona")
        for text in answers:
            client.post(f"/v1/conversations/{conversation}/messages", json={"text": text}, headers=headers)
    analyst = client.post("/v1/demo-analyst-session").json()["token"]
    counts = client.get("/v1/metrics", headers={"Authorization": f"Bearer {analyst}"}).json()["counts"]
    assert counts["conversations"] == 2 and counts["person_offered"] == 2
    assert counts["person_offer_taken"] == 1 and counts["ended_after_offer_done"] == 1
    assert counts["person_transferred"] == 1 and counts["handoffs_complaints"] == 1
    turns = [r for r in lines if r["event"] == "turn"]
    assert [r["person"] for r in turns] == ["offered", "offer_taken", None, None, "offered", "transferred"]


def test_if_the_classifier_cannot_start_the_rules_answer_and_health_says_degraded(monkeypatch, lines):
    def broken():
        raise MemoryError("not enough memory to fit the model")

    monkeypatch.setattr(ml.claims, "default_classifier", broken)
    settings = Settings(session_secret="test-secret", llm="classifier")
    client = TestClient(create_app(settings, build(settings, now=lambda: CLOCK)))
    health = client.get("/v1/health").json()
    assert health == {"status": "degraded", "llm_provider": "rules", "version": "dev"}
    assert any(r["event"] == "interpreter_fallback" for r in lines)
    _, conversation = converse(client, "No reconozco un cargo de Libreria Andina")
    assert conversation
