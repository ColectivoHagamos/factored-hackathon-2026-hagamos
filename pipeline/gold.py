"""Gold layer: exactly what the agent tools read, with the lineage of every row, in a read-only DuckDB file.

Tables:
- charges: purchases and bank adjustments, with the card, the merchant and whether it is a known merchant
  (an approved purchase by the same customer at the same merchant in the previous 365 days);
- cards: credit and debit cards with their status;
- customers: country, segment and status only;
- dispute_history: dispute complaints per customer, to count disputes in a window (POL-08, POL-17);
- exchange_rates: daily rates, kept for the path to production.

Usage: python -m pipeline.gold
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from pipeline.paths import ensure_outside_repo, lake_dir

TABLES = {
    "customers": """
        SELECT customer_id, country_code, segment, customer_status, birth_year, detected_accent, source_file
        FROM {customers}
    """,
    "cards": """
        SELECT product_id, customer_id, replace(product_type, '_card', '') AS card_type, card_last4, currency,
               status, expires_on, source_file
        FROM {products}
        WHERE product_type IN ('credit_card', 'debit_card')
    """,
    "charges": """
        SELECT t.transaction_id, t.customer_id, t.product_id,
               CASE t.transaction_type WHEN 'purchase' THEN 'purchase' ELSE 'bank_adjustment' END AS kind,
               t.occurred_at, t.amount, t.currency, t.amount_usd, t.merchant, t.merchant_category, t.city,
               t.country_code, t.status, p.product_type, p.card_last4, t.fraud_score, t.is_fraud,
               t.transaction_type = 'purchase' AND t.merchant IS NOT NULL AND coalesce(sum(
                   CASE WHEN t.status = 'approved' THEN 1 ELSE 0 END
               ) OVER (
                   PARTITION BY t.customer_id, t.merchant ORDER BY t.occurred_at
                   RANGE BETWEEN INTERVAL 365 DAYS PRECEDING AND INTERVAL 1 MICROSECOND PRECEDING
               ), 0) > 0 AS is_known_merchant,
               t.source_file
        FROM {transactions} AS t
        JOIN {products} AS p USING (product_id)
        WHERE t.transaction_type IN ('purchase', 'adjustment')
    """,
    "dispute_history": """
        SELECT complaint_id, customer_id, created_at, subcategory, status, source_file
        FROM {complaints}
        WHERE subcategory IN ('unrecognized_charge', 'improper_charge')
    """,
    "exchange_rates": """
        SELECT rate_date, source_currency, target_currency, rate, buy_rate, sell_rate, provider, source_file
        FROM {daily_exchange_rates}
    """,
}


def run(lake: Path, now: datetime | None = None) -> dict:
    """Rebuild gold.duckdb from silver and return its manifest; a failed build keeps the previous file."""
    lake = ensure_outside_repo(lake)
    gold = lake / "gold"
    gold.mkdir(parents=True, exist_ok=True)
    manifest_id = json.loads((lake / "bronze" / "manifest.json").read_text(encoding="utf-8"))["manifest_id"]
    target, building = gold / "gold.duckdb", gold / "gold.duckdb.building"
    building.unlink(missing_ok=True)
    con = duckdb.connect(str(building))
    try:
        manifest = _build(con, lake, manifest_id, now or datetime.now(UTC))
    except BaseException:
        con.close()
        building.unlink(missing_ok=True)
        raise
    con.close()
    building.replace(target)
    return manifest


def _build(con: duckdb.DuckDBPyConnection, lake: Path, manifest_id: str, now: datetime) -> dict:
    sources = {
        table: f"read_parquet('{lake / 'silver' / table}.parquet')"
        for table in ("customers", "products", "transactions", "complaints", "daily_exchange_rates")
    }
    counts = {}
    for name, query in TABLES.items():
        # Lineage: every row keeps its source file and the bronze manifest it was built from.
        con.execute(f"CREATE TABLE {name} AS SELECT *, '{manifest_id}' AS manifest_id FROM ({query.format(**sources)})")
        counts[name] = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
    # Freshness: the cut is the latest event in the data; the simulated clock of the policy must not precede it.
    cut = con.execute("SELECT max(occurred_at) FROM charges").fetchone()[0]
    manifest = {
        "bronze_manifest": manifest_id,
        "built_at": now.isoformat(),
        "data_cut": cut.isoformat() if cut else None,
        "rows": counts,
    }
    con.execute("CREATE TABLE gold_manifest AS SELECT $manifest AS manifest", {"manifest": json.dumps(manifest)})
    return manifest


def main() -> int:
    manifest = run(lake_dir())
    print("gold: " + ", ".join(f"{name} {rows}" for name, rows in manifest["rows"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
