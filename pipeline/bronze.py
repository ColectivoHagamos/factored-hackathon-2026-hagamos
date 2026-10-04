"""Bronze layer: a faithful, traceable copy of the source files, outside the repository.

Each source table becomes one Parquet file with every column kept as text, so no value is reinterpreted,
plus the relative path of the file each row came from. The manifest records file, size and SHA-256 of every
source file. A second run with unchanged sources rewrites nothing.

Usage: python -m pipeline.bronze [--sync-from-s3]
With --sync-from-s3 the sources are first synchronized with the AWS CLI, using the bucket in VERA_S3_BUCKET and
the local profile in AWS_PROFILE; no bucket name or credential is ever written to the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from pipeline.paths import ensure_outside_repo, lake_dir, source_dir

CHUNK = 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(CHUNK):
            digest.update(block)
    return digest.hexdigest()


def discover_tables(source: Path) -> dict[str, list[Path]]:
    """A top-level CSV is a table; a directory of CSV partitions is a table."""
    tables: dict[str, list[Path]] = {}
    for entry in sorted(source.iterdir()):
        if entry.is_file() and entry.suffix == ".csv":
            tables[entry.stem] = [entry]
        elif entry.is_dir():
            files = sorted(entry.rglob("*.csv"))
            if files:
                tables[entry.name] = files
    return tables


def describe_sources(source: Path, tables: dict[str, list[Path]]) -> dict[str, list[dict]]:
    return {
        name: [{"path": str(f.relative_to(source)), "bytes": f.stat().st_size, "sha256": sha256(f)} for f in files]
        for name, files in tables.items()
    }


def manifest_id(sources: dict[str, list[dict]]) -> str:
    canonical = json.dumps(sources, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def write_table(con: duckdb.DuckDBPyConnection, source: Path, name: str, files: list[Path], target: Path) -> int:
    """Copy one table to Parquet as text, with the relative source file of each row."""
    paths = [str(f) for f in files]
    prefix = str(source) + "/"
    relation = con.sql(
        "SELECT * REPLACE (replace(filename, $prefix, '') AS filename) FROM read_csv("
        "$paths, all_varchar = true, union_by_name = true, hive_partitioning = false, filename = true)",
        params={"paths": paths, "prefix": prefix},
    )
    relation.write_parquet(str(target), compression="zstd")
    return con.sql("SELECT count(*) FROM read_parquet($target)", params={"target": str(target)}).fetchone()[0]


def run(source: Path, lake: Path, now: datetime | None = None) -> dict:
    """Build or reuse the bronze layer and return its manifest."""
    source, lake = ensure_outside_repo(source), ensure_outside_repo(lake)
    bronze = lake / "bronze"
    bronze.mkdir(parents=True, exist_ok=True)
    manifest_path = bronze / "manifest.json"
    tables = discover_tables(source)
    sources = describe_sources(source, tables)
    current_id = manifest_id(sources)
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous["manifest_id"] == current_id and all((bronze / f"{n}.parquet").exists() for n in tables):
            return previous
    con = duckdb.connect()
    manifest = {
        "manifest_id": current_id,
        "loaded_at": (now or datetime.now(UTC)).isoformat(),
        "tables": {
            name: {
                "parquet": f"{name}.parquet",
                "rows": write_table(con, source, name, files, bronze / f"{name}.parquet"),
                "files": sources[name],
            }
            for name, files in tables.items()
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def sync_from_s3(source: Path) -> None:
    bucket = os.environ.get("VERA_S3_BUCKET")
    if not bucket:
        raise SystemExit("VERA_S3_BUCKET is required to synchronize from S3")
    subprocess.run(["aws", "s3", "sync", f"s3://{bucket}/", str(source), "--only-show-errors"], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the bronze layer with its manifest.")
    parser.add_argument("--sync-from-s3", action="store_true")
    args = parser.parse_args()
    source = ensure_outside_repo(source_dir())
    if args.sync_from_s3:
        sync_from_s3(source)
    manifest = run(source, lake_dir())
    rows = sum(table["rows"] for table in manifest["tables"].values())
    print(f"bronze: {len(manifest['tables'])} tables, {rows} rows, manifest {manifest['manifest_id'][:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
