"""The product around the conversation: the login of the jury and the team, the demo customers with invented names,
their cards and movements, and where the dispute stands in every reply."""

import pytest
from fastapi.testclient import TestClient

from api.access import Accounts, check_password, hash_password
from api.dependencies import build
from api.main import create_app
from api.personas import personas
from api.settings import Settings
from tests.contract.test_api import CO_01, CO_02, Clock, login, say
from vera.adapters.mock_bank import CUSTOMERS
from vera.contracts.api import MeResponse, Movement

PASSWORD = "una-clave-larga-de-prueba"


@pytest.fixture
def api() -> tuple[TestClient, Clock]:
    clock = Clock()
    settings = Settings(session_secret="test-secret", messages_per_minute=50)
    return TestClient(create_app(settings, build(settings, now=clock))), clock


@pytest.fixture
def closed() -> TestClient:
    """A deployment with accounts: nothing about the demo customers opens without the login."""
    settings = Settings(session_secret="test-secret", testers=f"jurado:{hash_password(PASSWORD)}")
    return TestClient(create_app(settings, build(settings, now=Clock())))


def access(client: TestClient) -> dict:
    token = client.post("/v1/auth/login", json={"username": "jurado", "password": PASSWORD}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_a_password_is_kept_only_as_a_salted_hash():
    stored = hash_password(PASSWORD)
    assert PASSWORD not in stored and "$" not in stored and stored != hash_password(PASSWORD)
    assert check_password(PASSWORD, stored) and not check_password("otra-clave", stored)
    assert not check_password(PASSWORD, "not-a-hash")


def test_accounts_are_read_from_the_setting_and_an_unknown_user_fails_like_a_wrong_password():
    testers = Accounts(f"jurado:{hash_password(PASSWORD)}, equipo:{hash_password('otra-clave-larga')}")
    assert not testers.open and testers.check("jurado", PASSWORD) and testers.check("equipo", "otra-clave-larga")
    assert not testers.check("jurado", "otra-clave-larga") and not testers.check("nadie", PASSWORD)
    assert Accounts("").open


def test_with_accounts_the_demo_needs_the_login(closed: TestClient):
    assert closed.get("/v1/demo-customers").status_code == 401
    assert closed.post("/v1/demo-session", json={"demo_customer": CO_01}).status_code == 401
    assert closed.post("/v1/demo-analyst-session").status_code == 401
    wrong = closed.post("/v1/auth/login", json={"username": "jurado", "password": "no-es-esta"})
    assert wrong.status_code == 401 and PASSWORD not in wrong.text
    headers = access(closed)
    assert closed.get("/v1/demo-customers", headers=headers).status_code == 200
    session = closed.post("/v1/demo-session", json={"demo_customer": CO_01}, headers=headers)
    assert session.status_code == 200
    # The access token never stands for a customer: a conversation needs the customer's own session.
    assert closed.post("/v1/conversations", json={}, headers=headers).status_code == 401


def test_logins_are_limited_per_minute(closed: TestClient):
    codes = [
        closed.post("/v1/auth/login", json={"username": "jurado", "password": "no-es-esta"}).status_code
        for _ in range(12)
    ]
    assert codes[:10] == [401] * 10 and codes[-1] == 429


def test_without_accounts_the_demo_stays_open(api):
    client, _ = api
    assert client.get("/v1/demo-customers").status_code == 200
    assert client.post("/v1/auth/login", json={"username": "dev", "password": "x"}).status_code == 200


def test_demo_customers_have_invented_names_that_never_repeat(api):
    client, _ = api
    customers = client.get("/v1/demo-customers").json()
    names = [c["display_name"] for c in customers]
    assert len(set(names)) == len(names) and all(c["first_name"] in c["display_name"] for c in customers)
    # The names live in the API layer; the bank records still hold none.
    assert not any(name.split()[0] in c.alias for name in names for c in CUSTOMERS)


def test_names_are_stable_and_portuguese_only_for_the_portuguese_scenario_alone():
    first, again = personas(CUSTOMERS), personas(tuple(reversed(CUSTOMERS)))
    assert first == again
    # CO-02 serves A2, A3, A6 and A9, so it keeps Spanish.
    assert first[CO_02].language.value == "es"


def test_the_greeting_calls_the_customer_by_name(api):
    client, _ = api
    start = client.post("/v1/conversations", json={}, headers=login(client)).json()
    first_name = next(c["first_name"] for c in client.get("/v1/demo-customers").json() if c["customer_ref"] == CO_01)
    assert start["greeting"].startswith(f"Hola, {first_name}, soy VERA")


def test_the_customer_sees_its_cards_and_its_movements_newest_first(api):
    client, _ = api
    headers = login(client)
    me = MeResponse.model_validate(client.get("/v1/me", headers=headers).json())
    assert me.alias.startswith("CO-01") and me.cards and me.cards[0].masked.startswith("••••")
    movements = [Movement.model_validate(m) for m in client.get("/v1/me/movements", headers=headers).json()]
    assert movements and movements == sorted(movements, key=lambda m: m.occurred_at, reverse=True)
    assert {m.card for m in movements if m.card} <= {card.masked for card in me.cards}
    other = [Movement.model_validate(m) for m in client.get("/v1/me/movements", headers=login(client, CO_02)).json()]
    assert not {(m.occurred_at, m.amount) for m in movements} & {(m.occurred_at, m.amount) for m in other}
    assert client.get("/v1/me").status_code == 401


def test_a_blocked_card_shows_as_blocked(api):
    client, _ = api
    headers = login(client)
    conversation = client.post("/v1/conversations", json={}, headers=headers).json()["conversation_id"]
    say(client, headers, conversation, text="Me robaron la tarjeta")
    say(client, headers, conversation, selected_option="yes")
    assert [card["status"] for card in client.get("/v1/me", headers=headers).json()["cards"]] == ["blocked"]


def test_every_reply_says_where_the_dispute_stands(api):
    client, _ = api
    headers = login(client)
    conversation = client.post("/v1/conversations", json={}, headers=headers).json()["conversation_id"]
    receipt = say(client, headers, conversation, text="No reconozco un cargo de Libreria Andina")
    assert receipt.stage == "analysis" and receipt.charge and receipt.charge.merchant == "Libreria Andina"
    stages = [receipt.stage]
    for text in ("no", "sí", "sí, la tengo", "todos"):
        stages.append(say(client, headers, conversation, text=text).stage)
    done = say(client, headers, conversation, selected_option="yes")
    assert stages[1:] == ["verification"] * 4 and done.case_id and done.case_id in done.reply
    assert done.stage in ("result", "resolved")
