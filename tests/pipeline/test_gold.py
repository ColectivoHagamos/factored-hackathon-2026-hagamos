"""Tests of the gold layer on generated files: tool tables, known merchants and lineage."""

import json
from pathlib import Path

import duckdb
import pytest

from pipeline import gold, silver


@pytest.fixture
def gold_db(lake: Path) -> duckdb.DuckDBPyConnection:
    silver.run(lake, report_path=None)
    gold.run(lake)
    con = duckdb.connect(str(lake / "gold" / "gold.duckdb"), read_only=True)
    yield con
    con.close()


def test_charges_hold_purchases_and_bank_adjustments_only(gold_db: duckdb.DuckDBPyConnection):
    kinds = dict(gold_db.execute("SELECT transaction_id, kind FROM charges ORDER BY 1").fetchall())
    assert kinds == {"T1": "purchase", "T6": "purchase", "T7": "purchase", "T8": "bank_adjustment"}


def test_known_merchant_needs_an_earlier_approved_purchase_within_a_year(gold_db: duckdb.DuckDBPyConnection):
    known = dict(gold_db.execute("SELECT transaction_id, is_known_merchant FROM charges").fetchall())
    assert known == {"T1": True, "T7": False, "T6": False, "T8": False}


def test_charges_carry_the_card_and_never_the_full_number(gold_db: duckdb.DuckDBPyConnection):
    cards = dict(gold_db.execute("SELECT transaction_id, card_last4 FROM charges").fetchall())
    assert cards == {"T1": "5678", "T7": "5678", "T6": "5678", "T8": None}
    columns = {row[0] for row in gold_db.execute("DESCRIBE cards").fetchall()}
    assert "product_number" not in columns and "card_last4" in columns


def test_dispute_history_keeps_only_dispute_complaints(gold_db: duckdb.DuckDBPyConnection):
    rows = gold_db.execute("SELECT complaint_id, subcategory FROM dispute_history ORDER BY 1").fetchall()
    assert rows == [("K1", "unrecognized_charge"), ("K2", "improper_charge")]


def test_every_row_keeps_its_lineage(gold_db: duckdb.DuckDBPyConnection, lake: Path):
    manifest_id = json.loads((lake / "bronze" / "manifest.json").read_text(encoding="utf-8"))["manifest_id"]
    for table in ("customers", "cards", "charges", "dispute_history", "exchange_rates"):
        missing = gold_db.execute(
            f"SELECT count(*) FROM {table} WHERE source_file IS NULL OR manifest_id <> $id", {"id": manifest_id}
        ).fetchone()[0]
        assert missing == 0, table
    stored = json.loads(gold_db.execute("SELECT manifest FROM gold_manifest").fetchone()[0])
    assert stored["bronze_manifest"] == manifest_id and stored["rows"]["charges"] == 4


def test_a_failed_build_leaves_the_previous_gold_in_place(lake: Path, monkeypatch: pytest.MonkeyPatch):
    silver.run(lake, report_path=None)
    gold.run(lake)
    before = (lake / "gold" / "gold.duckdb").stat().st_mtime_ns
    monkeypatch.setitem(gold.TABLES, "broken", "SELECT * FROM missing_table")
    with pytest.raises(duckdb.Error):
        gold.run(lake)
    assert (lake / "gold" / "gold.duckdb").stat().st_mtime_ns == before
    assert not (lake / "gold" / "gold.duckdb.building").exists()
