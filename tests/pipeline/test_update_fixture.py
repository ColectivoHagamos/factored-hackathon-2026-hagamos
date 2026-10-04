"""Update fixture (P10): a generated batch arrives after the cut; gold changes only where it should.

The batch has a new charge, a status change (pending to approved) and two invalid rows. No dataset record is used.
"""

import json
from pathlib import Path

import duckdb
import pytest

from pipeline import bronze, gold, silver
from tests.pipeline.conftest import TRANSACTION_HEADER, make_source, write

UPDATE_BATCH = [
    TRANSACTION_HEADER,
    # New charge after the cut.
    "T9,2026-06-19 10:00:00,2026-06-19,P1,C1,Purchase,Food,25000,COP,,POS,Store,Food,Colombia,Cali,Approved,00,False,4",
    # Status change: T6 was pending and is now approved; the later version wins.
    "T6,2026-06-16 03:00:00,2026-06-19,P4,C3,Purchase,Food,35000,ARS,,POS,,,Argentina,Rosario,Approved,00,False,5",
    # Invalid: unknown status.
    "T10,2026-06-19 11:00:00,2026-06-19,P2,C2,Payment,,10.00,USD,10.00,App,,,Mexico,CDMX,Lost,00,False,",
    # Invalid: product of no known customer.
    "T11,2026-06-19 12:00:00,2026-06-19,P99,C1,Purchase,Food,10,COP,,POS,Store,Food,Colombia,Cali,Approved,00,False,4",
]


def build(source: Path, lake: Path) -> dict:
    bronze.run(source, lake)
    silver.run(lake, report_path=None)
    return gold.run(lake)


def charges(lake: Path) -> dict[str, dict]:
    con = duckdb.connect(str(lake / "gold" / "gold.duckdb"), read_only=True)
    cursor = con.execute("SELECT * EXCLUDE (manifest_id) FROM charges")
    names = [column[0] for column in cursor.description]
    rows = {row[0]: dict(zip(names, row, strict=True)) for row in cursor.fetchall()}
    con.close()
    return rows


@pytest.fixture
def before_and_after(tmp_path: Path) -> tuple[dict, dict, dict, dict, Path]:
    source, lake = make_source(tmp_path / "data"), tmp_path / "lake"
    first = build(source, lake)
    before = charges(lake)
    write(source / "transactions/year=2026/month=06/day=19/part.csv", UPDATE_BATCH)
    second = build(source, lake)
    return first, second, before, charges(lake), lake


def test_gold_changes_only_where_the_batch_says(before_and_after):
    _, _, before, after, _ = before_and_after
    added = set(after) - set(before)
    changed = {key for key in set(before) & set(after) if before[key] != after[key]}
    assert added == {"T9"}
    assert changed == {"T6"}
    assert set(before) - set(after) == set()


def test_status_change_is_applied_from_the_later_version(before_and_after):
    _, _, before, after, _ = before_and_after
    assert before["T6"]["status"] == "pending" and after["T6"]["status"] == "approved"


def test_invalid_rows_of_the_batch_are_quarantined_with_their_reasons(before_and_after):
    *_, lake = before_and_after
    rows = duckdb.sql(
        f"SELECT transaction_id, reasons FROM '{lake}/quarantine/transactions.parquet' "
        "WHERE transaction_id IN ('T10', 'T11', 'T6') ORDER BY 1, process_date"
    ).fetchall()
    assert ("T10", ["status_is_known"]) in rows
    assert ("T11", ["orphan_product_id"]) in rows
    # The superseded pending version of T6 is kept in quarantine, not dropped silently.
    assert ("T6", ["duplicate_key"]) in rows


def test_the_cut_and_the_manifest_move_with_the_batch(before_and_after):
    first, second, *_ = before_and_after
    assert first["data_cut"].startswith("2026-06-16") and second["data_cut"].startswith("2026-06-19")
    assert first["bronze_manifest"] != second["bronze_manifest"]
    assert second["rows"]["charges"] == first["rows"]["charges"] + 1


def test_reloading_the_same_batch_changes_nothing(before_and_after, tmp_path: Path):
    *_, after, lake = before_and_after
    manifest = json.loads((lake / "bronze" / "manifest.json").read_text(encoding="utf-8"))
    assert bronze.run(tmp_path / "data", lake)["manifest_id"] == manifest["manifest_id"]
    silver.run(lake, report_path=None)
    gold.run(lake)
    assert charges(lake) == after
