"""Silver layer: typed rows that pass their contract; every other row goes to quarantine with its reasons.

Nothing is dropped silently: a row is either in silver or in quarantine, and the data quality report counts
each reason. The report holds counts only and is the one artifact of the pipeline that is versioned.

Usage: python -m pipeline.silver
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

from pipeline.contracts import CONTRACTS, TableContract
from pipeline.paths import REPO, ensure_outside_repo, lake_dir

REPORT = REPO / "docs" / "data_quality_report.json"


def _reasons(contract: TableContract, silver: Path) -> str:
    """SQL list of the reasons a raw row fails: blocking rules, repeated key and orphan references."""
    items = [
        f"CASE WHEN NOT coalesce(({rule.check}), false) THEN '{rule.name}' END" for rule in contract.blocking_rules
    ]
    items.append(
        f"CASE WHEN row_number() OVER (PARTITION BY {contract.key} ORDER BY {contract.keep_first_by}) > 1 "
        "THEN 'duplicate_key' END"
    )
    for ref in contract.references:
        also = "".join(f" AND parent.{parent} = raw.{child}" for child, parent in ref.also)
        parent_table = silver / f"{ref.table}.parquet"
        items.append(
            f"CASE WHEN NOT EXISTS (SELECT 1 FROM read_parquet('{parent_table}') AS parent "
            f"WHERE parent.{ref.key} = raw.{ref.column}{also}) THEN '{ref.name}' END"
        )
    return f"list_filter([{', '.join(items)}], reason -> reason IS NOT NULL)"


def _warnings(contract: TableContract) -> str:
    items = [f"CASE WHEN NOT coalesce(({rule.check}), false) THEN '{rule.name}' END" for rule in contract.warning_rules]
    return f"list_filter([{', '.join(items)}]::VARCHAR[], warning -> warning IS NOT NULL)" if items else "[]::VARCHAR[]"


def _counts(con: duckdb.DuckDBPyConnection, column: str) -> dict[str, int]:
    rows = con.execute(
        f"SELECT item, count(*) FROM (SELECT unnest({column}) AS item FROM staged) GROUP BY 1 ORDER BY 1"
    )
    return {name: count for name, count in rows.fetchall()}


def build_table(con: duckdb.DuckDBPyConnection, contract: TableContract, lake: Path) -> dict:
    """Validate one bronze table into silver and quarantine; return its section of the report."""
    bronze, silver, quarantine = lake / "bronze", lake / "silver", lake / "quarantine"
    con.execute(
        f"CREATE OR REPLACE TEMP TABLE staged AS SELECT raw.*, {_reasons(contract, silver)} AS reasons, "
        f"{_warnings(contract)} AS warnings FROM read_parquet('{bronze / contract.table}.parquet') AS raw"
    )
    typed = ", ".join(f"{expression} AS {name}" for name, expression in contract.columns.items())
    con.execute(
        f"COPY (SELECT {typed} FROM staged WHERE len(reasons) = 0) "
        f"TO '{silver / contract.table}.parquet' (FORMAT parquet, COMPRESSION zstd)"
    )
    con.execute(
        f"COPY (SELECT * EXCLUDE (warnings) FROM staged WHERE len(reasons) > 0) "
        f"TO '{quarantine / contract.table}.parquet' (FORMAT parquet, COMPRESSION zstd)"
    )
    total, valid = con.execute("SELECT count(*), count(*) FILTER (WHERE len(reasons) = 0) FROM staged").fetchone()
    metrics = {
        name: con.execute(f"SELECT {aggregate} FROM staged WHERE len(reasons) = 0").fetchone()[0]
        for name, aggregate in contract.metrics.items()
    }
    return {
        "rows_in": total,
        "rows_valid": valid,
        "rows_quarantined": total - valid,
        "quarantine_reasons": _counts(con, "reasons"),
        "warnings": _counts(con, "warnings"),
        "metrics": metrics,
    }


def run(lake: Path, report_path: Path | None = REPORT) -> dict:
    """Build every contracted table in dependency order and write the aggregated report."""
    lake = ensure_outside_repo(lake)
    for folder in ("silver", "quarantine"):
        (lake / folder).mkdir(parents=True, exist_ok=True)
    manifest = json.loads((lake / "bronze" / "manifest.json").read_text(encoding="utf-8"))
    con = duckdb.connect()
    tables = {contract.table: build_table(con, contract, lake) for contract in CONTRACTS}
    report = {
        "bronze_manifest": manifest["manifest_id"],
        "tables": tables,
        "bronze_only": sorted(set(manifest["tables"]) - set(tables)),
    }
    if report_path is not None:
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    report = run(lake_dir())
    for table, section in report["tables"].items():
        print(f"silver {table}: {section['rows_valid']} valid, {section['rows_quarantined']} quarantined")
    return 0


if __name__ == "__main__":
    sys.exit(main())
