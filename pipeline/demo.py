"""Pseudonymized demo subset: about forty customers that cover the acceptance scenarios, and nothing else.

- Identifiers are replaced by keyed pseudonyms (HMAC-SHA256); the key never leaves the building machine.
- Names, documents, contact data and addresses are absent; each customer gets an alias such as "CO-03 · plus".
- Cards are masked with invented digits; the fraud label is dropped and the score is reduced to its band.
- Amounts, currencies, dates, statuses, merchants and countries are kept: the legal clock and the evaluation need them.

Usage: python -m pipeline.demo
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb

from pipeline.paths import REPO, ensure_outside_repo, lake_dir
from pipeline.pseudonym import digest, invented_last4, key_path, load_or_create_key, pseudonym
from vera.policy.model import load_policy

REPORT = REPO / "docs" / "demo_subset_report.json"
PER_SCENARIO = 3
CHARGE_WINDOW_DAYS = 180
# POL-17 looks for the first dispute in twelve months.
DISPUTE_WINDOW_DAYS = 365
SCORE_THRESHOLD = load_policy().parameters.fraud_score_threshold

# Each query returns customer_id; {since_N} is the simulated clock minus N days.
SCENARIOS: dict[str, str] = {
    "A1_co_recent_domestic_purchase": """
        SELECT customer_id FROM charges JOIN customers USING (customer_id)
        WHERE customers.country_code = 'CO' AND charges.country_code = 'CO' AND kind = 'purchase'
          AND status = 'approved' AND merchant IS NOT NULL AND coalesce(fraud_score, 0) <= {threshold}
          AND occurred_at >= {since_7}""",
    "A2_pending_purchase": """
        SELECT customer_id FROM charges
        WHERE kind = 'purchase' AND status = 'pending' AND occurred_at >= {since_30}""",
    # The sweep needs two charges on the card; the signal comes from the conversation ("I do not have the card").
    "A3_card_with_two_recent_purchases": """
        SELECT customer_id FROM charges
        WHERE kind = 'purchase' AND status = 'approved' AND occurred_at >= {since_14}
        GROUP BY customer_id, product_id HAVING count(*) >= 2""",
    "A4_mx_charge_in_madrid": """
        SELECT customer_id FROM charges JOIN customers USING (customer_id)
        WHERE customers.country_code = 'MX' AND city = 'Madrid' AND kind = 'purchase'
          AND occurred_at >= {since_90}""",
    "A5_ar_credit_card_purchase": """
        SELECT customer_id FROM charges JOIN customers USING (customer_id)
        WHERE customers.country_code = 'AR' AND product_type = 'credit_card' AND kind = 'purchase'
          AND status = 'approved' AND occurred_at >= {since_30}""",
    "A6_co_charge_in_sao_paulo": """
        SELECT customer_id FROM charges JOIN customers USING (customer_id)
        WHERE customers.country_code = 'CO' AND city = 'São Paulo' AND kind = 'purchase'
          AND occurred_at >= {since_60}""",
    "A9_two_purchases_same_merchant": """
        SELECT customer_id FROM charges
        WHERE kind = 'purchase' AND status = 'approved' AND merchant IS NOT NULL AND occurred_at >= {since_30}
        GROUP BY customer_id, merchant HAVING count(*) >= 2""",
    "A10_bank_adjustment": """
        SELECT customer_id FROM charges
        WHERE kind = 'bank_adjustment' AND status = 'approved' AND occurred_at >= {since_60}""",
    "recent_high_fraud_score": """
        SELECT customer_id FROM charges
        WHERE kind = 'purchase' AND fraud_score > {threshold} AND occurred_at >= {since_14}""",
    "repeat_disputes_90_days": """
        SELECT customer_id FROM dispute_history WHERE created_at >= {since_90}
        GROUP BY customer_id HAVING count(*) >= 2""",
    "declined_purchase": """
        SELECT customer_id FROM charges
        WHERE kind = 'purchase' AND status = 'declined' AND occurred_at >= {since_30}""",
    "reversed_purchase": """
        SELECT customer_id FROM charges
        WHERE kind = 'purchase' AND status = 'reversed' AND occurred_at >= {since_30}""",
    "known_merchant_purchase": """
        SELECT customer_id FROM charges WHERE is_known_merchant AND occurred_at >= {since_14}""",
}
SEGMENTS = ("basic", "plus", "premium", "student")


def _since(clock: date) -> dict[str, str]:
    values = {f"since_{days}": f"TIMESTAMP '{clock - timedelta(days=days)}'" for days in (7, 14, 30, 60, 90)}
    return values | {"threshold": str(SCORE_THRESHOLD)}


def select_customers(con: duckdb.DuckDBPyConnection, key: bytes, clock: date) -> dict[str, list[str]]:
    """Customers per scenario, in a key-dependent order so the choice does not follow the source ids."""
    chosen: dict[str, list[str]] = {}
    taken: set[str] = set()
    for scenario, query in SCENARIOS.items():
        found = {row[0] for row in con.execute(query.format(**_since(clock))).fetchall()}
        ordered = sorted(found - taken, key=lambda customer: digest(key, "selection", customer))
        chosen[scenario] = ordered[:PER_SCENARIO]
        taken.update(chosen[scenario])
    for segment in SEGMENTS:
        rows = con.execute(
            f"SELECT DISTINCT customer_id FROM charges JOIN customers USING (customer_id) "
            f"WHERE segment = '{segment}' AND kind = 'purchase' AND occurred_at >= {_since(clock)['since_30']}"
        ).fetchall()
        ordered = sorted({row[0] for row in rows} - taken, key=lambda customer: digest(key, "selection", customer))
        chosen[f"segment_{segment}"] = ordered[:2]
        taken.update(chosen[f"segment_{segment}"])
    return chosen


def _age_band(birth_year: int | None, clock: date) -> str | None:
    if birth_year is None:
        return None
    age = clock.year - birth_year
    return "60+" if age >= 60 else "45-59" if age >= 45 else "30-44" if age >= 30 else "18-29"


def build(gold_path: Path, target: Path, key: bytes, clock: date) -> dict:
    """Write demo.duckdb and return the coverage summary (counts only)."""
    gold = duckdb.connect(str(gold_path), read_only=True)
    chosen = select_customers(gold, key, clock)
    customers = sorted({c for ids in chosen.values() for c in ids}, key=lambda c: digest(key, "selection", c))
    scenarios_of = {c: sorted(s for s, ids in chosen.items() if c in ids) for c in customers}
    since = clock - timedelta(days=CHARGE_WINDOW_DAYS)
    params = {"ids": customers, "since": since}
    customer_rows = gold.execute(
        "SELECT customer_id, country_code, segment, customer_status, birth_year FROM customers "
        "WHERE list_contains($ids, customer_id)",
        {"ids": customers},
    ).fetchall()
    card_rows = gold.execute(
        "SELECT product_id, customer_id, card_type, status, expires_on FROM cards "
        "WHERE list_contains($ids, customer_id)",
        {"ids": customers},
    ).fetchall()
    charge_rows = gold.execute(
        "SELECT transaction_id, customer_id, product_id, kind, occurred_at, amount, currency, amount_usd, merchant, "
        "merchant_category, city, country_code, status, product_type, fraud_score, is_known_merchant "
        "FROM charges WHERE list_contains($ids, customer_id) AND occurred_at >= $since",
        params,
    ).fetchall()
    dispute_rows = gold.execute(
        "SELECT complaint_id, customer_id, created_at, subcategory FROM dispute_history "
        "WHERE list_contains($ids, customer_id) AND created_at >= $since",
        {"ids": customers, "since": clock - timedelta(days=DISPUTE_WINDOW_DAYS)},
    ).fetchall()
    gold.close()

    building = target.with_suffix(".building")
    building.unlink(missing_ok=True)
    con = duckdb.connect(str(building))
    try:
        _write(con, key, clock, customer_rows, card_rows, charge_rows, dispute_rows, scenarios_of)
    except BaseException:
        con.close()
        building.unlink(missing_ok=True)
        raise
    con.close()
    building.replace(target)
    by_country: dict[str, int] = {}
    by_segment: dict[str, int] = {}
    for _, country, segment, _, _ in customer_rows:
        by_country[country] = by_country.get(country, 0) + 1
        by_segment[segment] = by_segment.get(segment, 0) + 1
    return {
        "clock": clock.isoformat(),
        "charge_window_days": CHARGE_WINDOW_DAYS,
        "dispute_window_days": DISPUTE_WINDOW_DAYS,
        "customers": len(customer_rows),
        "cards": len(card_rows),
        "charges": len(charge_rows),
        "disputes": len(dispute_rows),
        "customers_per_scenario": {scenario: len(ids) for scenario, ids in chosen.items()},
        "customers_per_country": dict(sorted(by_country.items())),
        "customers_per_segment": dict(sorted(by_segment.items())),
    }


def _insert_many(con: duckdb.DuckDBPyConnection, sql: str, rows: list[list]) -> None:
    if rows:
        con.executemany(sql, rows)


def _write(con, key, clock, customer_rows, card_rows, charge_rows, dispute_rows, scenarios_of) -> None:
    con.execute(
        "CREATE TABLE customers (customer_ref VARCHAR PRIMARY KEY, alias VARCHAR, country_code VARCHAR, "
        "segment VARCHAR, customer_status VARCHAR, age_band VARCHAR, scenarios VARCHAR[])"
    )
    counters: dict[str, int] = {}
    for customer_id, country, segment, status, birth_year in sorted(
        customer_rows, key=lambda row: digest(key, "selection", row[0])
    ):
        counters[country] = counters.get(country, 0) + 1
        con.execute(
            "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                pseudonym(key, "customer", customer_id),
                f"{country}-{counters[country]:02d} · {segment}",
                country,
                segment,
                status,
                _age_band(birth_year, clock),
                scenarios_of[customer_id],
            ],
        )
    con.execute(
        "CREATE TABLE cards (card_ref VARCHAR PRIMARY KEY, customer_ref VARCHAR, card_type VARCHAR, "
        "masked_card VARCHAR, status VARCHAR, expires_on DATE)"
    )
    _insert_many(
        con,
        "INSERT INTO cards VALUES (?, ?, ?, ?, ?, ?)",
        [
            [
                pseudonym(key, "product", product_id),
                pseudonym(key, "customer", customer_id),
                card_type,
                f"•••• {invented_last4(key, product_id)}",
                status,
                expires_on,
            ]
            for product_id, customer_id, card_type, status, expires_on in card_rows
        ],
    )
    con.execute(
        "CREATE TABLE charges (charge_ref VARCHAR PRIMARY KEY, customer_ref VARCHAR, card_ref VARCHAR, "
        "product_type VARCHAR, kind VARCHAR, occurred_at TIMESTAMP, amount DECIMAL(18, 2), currency VARCHAR, "
        "amount_usd DECIMAL(18, 2), merchant VARCHAR, merchant_category VARCHAR, city VARCHAR, country_code VARCHAR, "
        "status VARCHAR, fraud_score_band VARCHAR, is_known_merchant BOOLEAN)"
    )
    _insert_many(
        con,
        "INSERT INTO charges VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            [
                pseudonym(key, "transaction", transaction_id),
                pseudonym(key, "customer", customer_id),
                pseudonym(key, "product", product_id) if product_type in ("credit_card", "debit_card") else None,
                product_type,
                kind,
                occurred_at,
                amount,
                currency,
                amount_usd,
                merchant,
                merchant_category,
                city,
                country_code,
                status,
                "none" if score is None else (">30" if score > SCORE_THRESHOLD else "<=30"),
                known,
            ]
            for (
                transaction_id,
                customer_id,
                product_id,
                kind,
                occurred_at,
                amount,
                currency,
                amount_usd,
                merchant,
                merchant_category,
                city,
                country_code,
                status,
                product_type,
                score,
                known,
            ) in charge_rows
        ],
    )
    con.execute(
        "CREATE TABLE disputes (dispute_ref VARCHAR PRIMARY KEY, customer_ref VARCHAR, created_at TIMESTAMP, "
        "subcategory VARCHAR)"
    )
    _insert_many(
        con,
        "INSERT INTO disputes VALUES (?, ?, ?, ?)",
        [
            [
                pseudonym(key, "complaint", complaint_id),
                pseudonym(key, "customer", customer_id),
                created_at,
                subcategory,
            ]
            for complaint_id, customer_id, created_at, subcategory in dispute_rows
        ],
    )


def run(lake: Path, key_file: Path, report_path: Path | None = REPORT) -> dict:
    lake = ensure_outside_repo(lake)
    (lake / "demo").mkdir(parents=True, exist_ok=True)
    clock = load_policy().parameters.system_clock
    summary = build(lake / "gold" / "gold.duckdb", lake / "demo" / "demo.duckdb", load_or_create_key(key_file), clock)
    if report_path is not None:
        report_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    summary = run(lake_dir(), key_path())
    print(
        f"demo: {summary['customers']} customers, {summary['cards']} cards, {summary['charges']} charges, "
        f"{summary['disputes']} disputes"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
