"""Tests of the bronze layer on generated files; no dataset record is used."""

import json
from pathlib import Path

import duckdb
import pytest

from pipeline.bronze import discover_tables, run
from pipeline.paths import REPO, ensure_outside_repo


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    write(root / "customers.csv", "customer_id,country\nC1,Colombia\nC2,México\n")
    write(root / "transactions/year=2026/month=06/day=17/part.csv", "transaction_id,amount\nT1,10.50\nT2,007\n")
    write(root / "transactions/year=2026/month=06/day=18/part.csv", "transaction_id,amount\nT3,20\n")
    write(root / "notes.txt", "not a table")
    return root


def test_tables_are_flat_files_or_partitioned_folders(source: Path):
    tables = discover_tables(source)
    assert sorted(tables) == ["customers", "transactions"]
    assert len(tables["transactions"]) == 2


def test_bronze_keeps_values_as_text_with_their_source_file(source: Path, tmp_path: Path):
    manifest = run(source, tmp_path / "lake")
    assert manifest["tables"]["transactions"]["rows"] == 3
    assert {f["path"] for f in manifest["tables"]["transactions"]["files"]} == {
        "transactions/year=2026/month=06/day=17/part.csv",
        "transactions/year=2026/month=06/day=18/part.csv",
    }
    assert all(len(f["sha256"]) == 64 and f["bytes"] > 0 for f in manifest["tables"]["customers"]["files"])
    rows = duckdb.sql(
        f"SELECT amount, filename FROM '{tmp_path}/lake/bronze/transactions.parquet' ORDER BY 1"
    ).fetchall()
    # Leading zeros survive: bronze never reinterprets a value.
    assert rows[0] == ("007", "transactions/year=2026/month=06/day=17/part.csv")


def test_second_run_with_unchanged_sources_rewrites_nothing(source: Path, tmp_path: Path):
    first = run(source, tmp_path / "lake")
    parquet = tmp_path / "lake/bronze/customers.parquet"
    written = parquet.stat().st_mtime_ns
    assert run(source, tmp_path / "lake") == first
    assert parquet.stat().st_mtime_ns == written


def test_a_changed_source_file_produces_a_new_manifest(source: Path, tmp_path: Path):
    first = run(source, tmp_path / "lake")
    write(source / "customers.csv", "customer_id,country\nC1,Colombia\nC2,México\nC3,Argentina\n")
    second = run(source, tmp_path / "lake")
    assert second["manifest_id"] != first["manifest_id"]
    assert second["tables"]["customers"]["rows"] == 3
    saved = json.loads((tmp_path / "lake/bronze/manifest.json").read_text(encoding="utf-8"))
    assert saved["manifest_id"] == second["manifest_id"]


def test_data_inside_the_repository_is_refused():
    with pytest.raises(ValueError, match="outside the repository"):
        ensure_outside_repo(REPO / "data")
