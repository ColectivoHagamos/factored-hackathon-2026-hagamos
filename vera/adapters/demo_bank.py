"""Bank adapter over the pseudonymized demo subset (read-only DuckDB); card blocks live in the writable state."""

from datetime import datetime
from pathlib import Path

import duckdb

from vera.adapters.sqlite_state import SqliteState
from vera.contracts.charges import ChargeKind, ChargeStatus, FraudScoreBand
from vera.contracts.common import Country, Currency
from vera.ports.bank import CardRecord, ChargeRecord, CustomerRecord

CHARGE_COLUMNS = (
    "charge_ref, customer_ref, card_ref, kind, occurred_at, amount, currency, amount_usd, merchant, "
    "merchant_category, city, country_code, status, fraud_score_band, is_known_merchant"
)


class DemoBank:
    def __init__(self, path: str | Path, state: SqliteState) -> None:
        self._connection = duckdb.connect(str(path), read_only=True)
        self._state = state

    def customer(self, customer_ref: str) -> CustomerRecord | None:
        row = self._connection.execute(
            "SELECT customer_ref, alias, country_code, segment, age_band FROM customers WHERE customer_ref = ?",
            [customer_ref],
        ).fetchone()
        return _customer(row) if row else None

    def customers(self) -> tuple[CustomerRecord, ...]:
        rows = self._connection.execute(
            "SELECT customer_ref, alias, country_code, segment, age_band FROM customers ORDER BY alias"
        ).fetchall()
        return tuple(_customer(row) for row in rows)

    def charges(self, customer_ref: str, since: datetime, until: datetime) -> tuple[ChargeRecord, ...]:
        rows = self._connection.execute(
            f"SELECT {CHARGE_COLUMNS} FROM charges WHERE customer_ref = ? AND occurred_at >= ? AND occurred_at <= ? "
            "ORDER BY occurred_at",
            [customer_ref, since, until],
        ).fetchall()
        return tuple(_charge(row) for row in rows)

    def disputes_since(self, customer_ref: str, since: datetime) -> int:
        return self._connection.execute(
            "SELECT count(*) FROM disputes WHERE customer_ref = ? AND created_at >= ?", [customer_ref, since]
        ).fetchone()[0]

    def cards(self, customer_ref: str) -> tuple[CardRecord, ...]:
        rows = self._connection.execute(
            "SELECT card_ref, customer_ref, card_type, masked_card, status FROM cards WHERE customer_ref = ? "
            "ORDER BY card_ref",
            [customer_ref],
        ).fetchall()
        blocked = self._state.blocked_cards()
        return tuple(CardRecord(*row[:4], "blocked" if row[0] in blocked else row[4]) for row in rows)

    def block(self, card_ref: str, idempotency_key: str) -> None:
        self._state.record_block(card_ref, idempotency_key)


def _customer(row: tuple) -> CustomerRecord:
    ref, alias, country, segment, age_band = row
    return CustomerRecord(ref, alias, Country(country), segment, age_band)


def _charge(row: tuple) -> ChargeRecord:
    ref, customer, card, kind, occurred_at, amount, currency, amount_usd, *place, status, band, known = row
    return ChargeRecord(
        ref,
        customer,
        card,
        ChargeKind(kind),
        occurred_at,
        amount,
        Currency(currency),
        amount_usd,
        *place,
        ChargeStatus(status),
        FraudScoreBand(band),
        bool(known),
    )
