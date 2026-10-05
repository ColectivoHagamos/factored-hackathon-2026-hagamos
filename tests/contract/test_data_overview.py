"""The page that shows a reviewer the data behind the demo: totals only, behind the login, never a record."""

from fastapi.testclient import TestClient

from api.access import hash_password
from api.dependencies import build
from api.main import create_app
from api.schemas import DataOverview
from api.settings import Settings
from tests.contract.test_api import Clock
from vera.adapters.mock_bank import CARDS, CHARGES, CUSTOMERS

PASSWORD = "una-clave-larga-de-prueba"


def closed() -> TestClient:
    settings = Settings(session_secret="test-secret", testers=f"demo:{hash_password(PASSWORD)}")
    return TestClient(create_app(settings, build(settings, now=Clock())))


def test_the_data_page_needs_the_login():
    assert closed().get("/v1/data/overview").status_code == 401


def test_the_overview_counts_the_subset_and_shows_the_source_tables():
    client = closed()
    token = client.post("/v1/auth/login", json={"username": "demo", "password": PASSWORD}).json()["token"]
    response = client.get("/v1/data/overview", headers={"Authorization": f"Bearer {token}"})
    overview = DataOverview.model_validate(response.json())
    subset = overview.subset
    assert subset.customers == len(CUSTOMERS) and subset.cards == len(CARDS) and subset.movements == len(CHARGES)
    assert sum(count.count for count in subset.customers_by_country) == len(CUSTOMERS)
    assert sum(count.count for count in subset.movements_by_status) == len(CHARGES)
    # The pipeline's own report: the tables of the Factored dataset and how many rows each contract let through.
    assert {"customers", "transactions"} <= {table.name for table in overview.source_tables}
    assert all(table.rows_valid + table.rows_quarantined == table.rows_in for table in overview.source_tables)


def test_no_reference_of_a_customer_card_or_movement_leaves():
    client = closed()
    token = client.post("/v1/auth/login", json={"username": "demo", "password": PASSWORD}).json()["token"]
    body = client.get("/v1/data/overview", headers={"Authorization": f"Bearer {token}"}).text
    references = [c.customer_ref for c in CUSTOMERS] + [c.card_ref for c in CARDS] + [c.charge_ref for c in CHARGES]
    assert not any(reference in body for reference in references)
    assert "CUS-" not in body and "PRD-" not in body
