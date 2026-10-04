"""Contract tests of the bank ports: the demo-subset adapter and the mock adapter pass the same tests."""

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from pipeline import bronze, demo, gold, silver
from tests.pipeline.conftest import make_source
from vera.adapters.demo_bank import DemoBank
from vera.adapters.mock_bank import MockBank
from vera.adapters.sqlite_state import SqliteState
from vera.contracts.charges import ChargeKind, ChargeStatus, FraudScoreBand
from vera.contracts.common import Country, Currency

SINCE, UNTIL = datetime(2025, 1, 1), datetime(2026, 6, 30)


@pytest.fixture(scope="module")
def demo_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("bank")
    source, lake = make_source(root / "data"), root / "lake"
    bronze.run(source, lake)
    silver.run(lake, report_path=None)
    gold.run(lake)
    key = root / "secrets" / "demo.key"
    key.parent.mkdir()
    key.write_text(bytes(range(32)).hex(), encoding="utf-8")
    demo.run(lake, key, report_path=None)
    return lake / "demo" / "demo.duckdb"


@pytest.fixture(params=["mock", "demo"])
def bank(request, demo_db: Path) -> Iterator:
    state = SqliteState()
    yield MockBank(state) if request.param == "mock" else DemoBank(demo_db, state)
    state.close()


def test_customers_have_a_country_and_an_alias_without_names(bank):
    customers = bank.customers()
    assert customers
    for customer in customers:
        assert isinstance(customer.country, Country) and " · " in customer.alias
        assert bank.customer(customer.customer_ref) == customer
    assert bank.customer("CUS-DOES-NOT-EXIST") is None


def test_charges_belong_to_their_customer_are_typed_and_ordered(bank):
    for customer in bank.customers():
        charges = bank.charges(customer.customer_ref, SINCE, UNTIL)
        assert all(charge.customer_ref == customer.customer_ref for charge in charges)
        assert [c.occurred_at for c in charges] == sorted(c.occurred_at for c in charges)
        for charge in charges:
            assert isinstance(charge.kind, ChargeKind) and isinstance(charge.status, ChargeStatus)
            assert isinstance(charge.currency, Currency) and isinstance(charge.fraud_score_band, FraudScoreBand)
            assert (charge.card_ref is None) == (charge.kind is ChargeKind.BANK_ADJUSTMENT)


def test_cards_are_masked_and_blocking_is_idempotent(bank):
    customer = next(c for c in bank.customers() if bank.cards(c.customer_ref))
    card = bank.cards(customer.customer_ref)[0]
    assert card.masked_card.startswith("•••• ") and len(card.masked_card) == 9
    bank.block(card.card_ref, idempotency_key="k-1")
    bank.block(card.card_ref, idempotency_key="k-2")
    assert [c.status for c in bank.cards(customer.customer_ref) if c.card_ref == card.card_ref] == ["blocked"]


def test_disputes_are_counted_per_customer(bank):
    for customer in bank.customers():
        assert bank.disputes_since(customer.customer_ref, SINCE) >= 0
