"""Tests of the silver layer: contracts, quarantine with reasons, deduplication and the quality report."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from pipeline import silver
from pipeline.contracts import CONTRACTS


@pytest.fixture
def report(lake: Path) -> dict:
    return silver.run(lake, report_path=None)


def rows(lake: Path, layer: str, table: str, columns: str, order: str = "1") -> list[tuple]:
    return duckdb.sql(f"SELECT {columns} FROM '{lake}/{layer}/{table}.parquet' ORDER BY {order}").fetchall()


def test_every_row_is_either_in_silver_or_in_quarantine(report: dict):
    for section in report["tables"].values():
        assert section["rows_valid"] + section["rows_quarantined"] == section["rows_in"]


def test_invalid_rows_are_quarantined_with_their_reasons(lake: Path, report: dict):
    reasons = dict(rows(lake, "quarantine", "transactions", "transaction_id, reasons"))
    assert reasons == {
        "T1": ["duplicate_key"],
        "T3": ["amount_is_a_non_negative_number"],
        "T4": ["currency_is_known"],
        "T5": ["orphan_product_id"],
    }
    assert report["tables"]["transactions"]["quarantine_reasons"]["currency_is_known"] == 1
    assert rows(lake, "quarantine", "customers", "customer_id, reasons") == [("C4", ["segment_is_known"])]
    assert rows(lake, "quarantine", "products", "product_id, reasons") == [("P3", ["orphan_customer_id"])]


def test_the_latest_processed_version_of_a_repeated_key_is_kept(lake: Path, report: dict):
    assert rows(lake, "silver", "transactions", "transaction_id, processed_on")[0] == ("T1", date(2026, 6, 15))


def test_values_are_typed_normalized_and_minimized(lake: Path, report: dict):
    t1, t2, t6 = rows(lake, "silver", "transactions", "transaction_id, country_code, amount_usd, amount_usd_imputed")
    assert t1 == ("T1", "BR", Decimal("30.00"), True)
    assert t2 == ("T2", "MX", Decimal("50.00"), False)
    assert t6 == ("T6", "AR", Decimal("100.00"), True)
    assert report["tables"]["transactions"]["metrics"] == {
        "amount_usd_copied_from_usd_amount": 0,
        "amount_usd_imputed_with_fixed_rate": 2,
        "event_on_day_after_process_date": 1,
    }
    columns = {name for name, *_ in duckdb.sql(f"DESCRIBE SELECT * FROM '{lake}/silver/customers.parquet'").fetchall()}
    assert "first_name" not in columns and {"customer_id", "country_code", "segment", "birth_year"} <= columns
    cards = rows(lake, "silver", "products", "product_id, card_last4")
    assert cards == [("P1", "5678"), ("P2", None), ("P4", "5678")]


def test_warnings_are_counted_without_quarantining(lake: Path, report: dict):
    assert report["tables"]["transactions"]["warnings"] == {"purchase_has_merchant": 1}
    assert report["tables"]["complaints"]["warnings"] == {"currency_used_by_transactions": 1}
    assert [r[0] for r in rows(lake, "silver", "complaints", "complaint_id")] == ["K1", "K2"]


def test_report_lists_bronze_only_tables_and_holds_counts_only(report: dict):
    assert report["bronze_only"] == ["branches"]
    assert set(report["tables"]) == {contract.table for contract in CONTRACTS}
    assert report["tables"]["daily_exchange_rates"]["quarantine_reasons"] == {"rate_is_positive": 1}
