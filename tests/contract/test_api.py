"""Contract tests of the HTTP API /v1 on the mock adapter (P19)."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from api.dependencies import build
from api.main import create_app
from api.settings import Settings
from vera.adapters.mock_bank import CLOCK
from vera.contracts.api import ApiError, MessageResponse
from vera.contracts.handoff import Handoff

CO_01, CO_02 = "CUS-MOCK00000000001", "CUS-MOCK00000000002"


class Clock:
    def __init__(self) -> None:
        self.now = CLOCK

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def world():
    clock = Clock()
    settings = Settings(session_secret="test-secret", messages_per_minute=50)
    container = build(settings, now=clock)
    return TestClient(create_app(settings, container)), clock, container


@pytest.fixture
def api(world) -> tuple[TestClient, Clock]:
    client, clock, _ = world
    return client, clock


def login(client: TestClient, customer: str = CO_01) -> dict:
    token = client.post("/v1/demo-session", json={"demo_customer": customer}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def say(client: TestClient, headers: dict, conversation: str, **body) -> MessageResponse:
    response = client.post(f"/v1/conversations/{conversation}/messages", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return MessageResponse.model_validate(response.json())


def test_demo_customers_are_listed_by_alias(api):
    client, _ = api
    customers = client.get("/v1/demo-customers").json()
    assert {c["alias"] for c in customers} >= {"CO-01 · plus", "AR-01 · basic"}


def test_a_full_dispute_over_http(api):
    client, _ = api
    headers = login(client)
    start = client.post("/v1/conversations", json={}, headers=headers).json()
    conversation = start["conversation_id"]
    assert "inteligencia artificial" in start["greeting"]
    assert [option["answer"] for option in start["options"]][2] == "lost_card"
    for text in ("No reconozco un cargo de Libreria Andina", "no", "sí", "sí, la tengo", "todos"):
        say(client, headers, conversation, text=text)
    done = say(client, headers, conversation, selected_option="yes")
    case_id = next(word for word in done.reply.split() if word.startswith("DSP-"))
    view = client.get(f"/v1/cases/{case_id}", headers=headers)
    assert view.status_code == 200 and view.json()["case"]["case_id"] == case_id


def test_missing_forged_or_expired_sessions_get_401(api):
    client, clock = api
    assert client.post("/v1/conversations", json={}).status_code == 401
    forged = {"Authorization": "Bearer abc.def"}
    assert client.post("/v1/conversations", json={}, headers=forged).status_code == 401
    headers = login(client)
    clock.now += timedelta(minutes=16)
    response = client.post("/v1/conversations", json={}, headers=headers)
    assert response.status_code == 401 and ApiError.model_validate(response.json()).code == "unauthorized"


def test_a_document_number_does_not_open_a_session(api):
    client, _ = api
    assert client.post("/v1/demo-session", json={"demo_customer": "1020304050"}).status_code == 404


def test_another_customers_conversation_and_case_read_as_not_found(api):
    client, _ = api
    owner = login(client, CO_02)
    conversation = client.post("/v1/conversations", json={}, headers=owner).json()["conversation_id"]
    stranger = login(client, CO_01)
    foreign = client.post(f"/v1/conversations/{conversation}/messages", json={"text": "hola"}, headers=stranger)
    missing = client.post("/v1/conversations/doesnotexist/messages", json={"text": "hola"}, headers=stranger)
    assert foreign.status_code == missing.status_code == 404 and foreign.json() == missing.json()
    assert client.get("/v1/cases/DSP-000001", headers=stranger).status_code == 404
    assert client.get("/v1/cases/not-a-case", headers=stranger).status_code == 404


def test_the_analyst_queue_lists_transfers_and_customers_cannot_read_it(api):
    client, _ = api
    headers = login(client, CO_01)
    conversation = client.post("/v1/conversations", json={}, headers=headers).json()["conversation_id"]
    say(client, headers, conversation, text="Quiero hablar con una persona")
    say(client, headers, conversation, text="no")
    analyst = {"Authorization": f"Bearer {client.post('/v1/demo-analyst-session').json()['token']}"}
    assert client.get("/v1/queue", headers=headers).status_code == 401
    [item] = client.get("/v1/queue", headers=analyst).json()
    assert (item["kind"], item["queue"], item["trace_id"]) == ("transfer", "complaints", f"trace-{conversation}")
    # The parts of the summary come as codes, for a console in any language.
    assert (item["reason"], item["charge_count"], item["pending_action"]) == ("person_requested", 0, None)
    path = f"/v1/transfers/{item['reference']}"
    assert client.get(path, headers=headers).status_code == 401
    assert client.get(path, headers=analyst).json()["reason"] == "person_requested"
    assert client.get("/v1/transfers/TRF-999999", headers=analyst).status_code == 404


def test_handoff_needs_the_analyst_role(api):
    client, _ = api
    headers = login(client, CO_02)
    conversation = client.post("/v1/conversations", json={}, headers=headers).json()["conversation_id"]
    for message in ("No reconozco un cargo de Uber", 2, "no", "sí", "no tengo la tarjeta", "no reconozco ninguno"):
        key = "selected_option" if isinstance(message, int) else "text"
        say(client, headers, conversation, **{key: message})
    say(client, headers, conversation, selected_option="yes")
    done = say(client, headers, conversation, selected_option="yes")
    case_id = next(word.strip(".") for word in done.reply.split() if word.startswith("DSP-"))
    assert client.get(f"/v1/cases/{case_id}/handoff", headers=headers).status_code == 401
    analyst = client.post("/v1/demo-analyst-session").json()["token"]
    handoff = client.get(f"/v1/cases/{case_id}/handoff", headers={"Authorization": f"Bearer {analyst}"})
    read = Handoff.model_validate(handoff.json())
    assert handoff.status_code == 200 and read.suggested_queue == "fraud"
    # The rules that decided the conversation reach the analyst: the sweep, the block and the registration.
    assert read.rules_applied == ("POL-05", "POL-06", "POL-16")
    [item] = client.get("/v1/queue", headers={"Authorization": f"Bearer {analyst}"}).json()
    # The sweep brought the two other charges the customer did not recognize into the one case.
    assert (item["claim_type"], item["reason"], item["charge_count"]) == ("unrecognized_charge", "fraud", 3)


def test_card_numbers_are_masked_before_the_conversation_sees_them(world):
    client, _, container = world
    headers = login(client)
    conversation = client.post("/v1/conversations", json={}, headers=headers).json()["conversation_id"]
    say(client, headers, conversation, text="mi tarjeta es 4000 1234 5678 9010, no reconozco un cargo")
    stored = str([event.data for event in container.conversation.history(conversation)])
    assert "4000 1234 5678 9010" not in stored and "5678" not in stored and "•••• 9010" in stored


def test_rate_limit_answers_429(api):
    client, _ = api
    headers = login(client)
    conversation = client.post("/v1/conversations", json={}, headers=headers).json()["conversation_id"]
    statuses = [
        client.post(f"/v1/conversations/{conversation}/messages", json={"text": "hola"}, headers=headers).status_code
        for _ in range(55)
    ]
    assert statuses.count(429) >= 1


def test_openapi_lists_every_endpoint(api):
    client, _ = api
    paths = set(client.get("/v1/openapi.json").json()["paths"])
    assert {
        "/v1/health",
        "/v1/demo-session",
        "/v1/conversations",
        "/v1/conversations/{conversation_id}/messages",
        "/v1/cases/{case_id}",
        "/v1/cases/{case_id}/handoff",
    } <= paths


@pytest.fixture
def web(tmp_path) -> TestClient:
    """A deployment with a built web: an index page and one hashed asset."""
    (tmp_path / "assets").mkdir()
    page = '<!doctype html><div id="root"></div><script type="module" src="/assets/app-1a2b.js"></script>'
    (tmp_path / "index.html").write_text(page)
    (tmp_path / "assets" / "app-1a2b.js").write_text("export {};")
    settings = Settings(session_secret="test-secret", web_dir=str(tmp_path))
    return TestClient(create_app(settings, build(settings, now=Clock())))


def test_every_page_of_the_web_answers_with_the_app(web):
    for page in ("/", "/login", "/clientes", "/banca", "/chat", "/analista"):
        response = web.get(page)
        assert response.status_code == 200 and 'id="root"' in response.text
        assert response.headers["cache-control"] == "no-cache"
    asset = web.get("/assets/app-1a2b.js")
    assert asset.status_code == 200 and "immutable" in asset.headers["cache-control"]


def test_a_missing_file_or_api_route_is_not_answered_with_the_app(web):
    assert web.get("/assets/missing.js").status_code == 404
    missing = web.get("/v1/nothing-here")
    assert missing.status_code == 404 and 'id="root"' not in missing.text


def test_the_old_console_address_leads_to_the_analyst_page(web):
    moved = web.get("/console.html", follow_redirects=False)
    assert moved.status_code == 308 and moved.headers["location"] == "/analista"


def test_the_sweep_reply_allows_several_options(api):
    client, _ = api
    headers = login(client)
    conversation = client.post("/v1/conversations", json={}, headers=headers).json()["conversation_id"]
    for text in ("No reconozco un cargo de Libreria Andina", "no", "sí"):
        say(client, headers, conversation, text=text)
    sweep = say(client, headers, conversation, text="sí, la tengo")
    assert sweep.multiple_choice and sweep.options


def test_a_configured_analyst_key_closes_the_demo_analyst_session():
    settings = Settings(session_secret="test-secret", analyst_key="k3y")
    client = TestClient(create_app(settings, build(settings, now=Clock())))
    assert client.post("/v1/demo-analyst-session").status_code == 401
    assert client.post("/v1/demo-analyst-session", headers={"X-Analyst-Key": "k3y"}).status_code == 200


def test_an_unexpected_failure_is_a_503_without_internals(world):
    _, _, container = world

    def broken():
        raise RuntimeError("database file is locked at /state/vera.db")

    container.customers.customers = broken
    client = TestClient(create_app(container.settings, container), raise_server_exceptions=False)
    response = client.get("/v1/demo-customers")
    assert response.status_code == 503 and response.json()["code"] == "provider_unavailable"
    assert "locked" not in response.text and "/state" not in response.text
