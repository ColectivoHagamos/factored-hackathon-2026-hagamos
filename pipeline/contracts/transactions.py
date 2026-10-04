"""Transactions. amount_usd is completed with the fixed rates of the policy when the source leaves it empty."""

from decimal import Decimal

from pipeline.contracts.base import Reference, Rule, TableContract, country_code, is_blank, known_country
from vera.policy.model import load_policy

RATES: dict[str, Decimal] = {currency.value: rate for currency, rate in load_policy().parameters.usd_rates.items()}
TYPES = ("Purchase", "Withdrawal", "Transfer", "Payment", "Deposit", "Adjustment")
STATUSES = ("Approved", "Declined", "Pending", "Reversed")

_amount = "CAST(amount AS DECIMAL(18, 2))"
_rate_cases = " ".join(f"WHEN '{currency}' THEN {rate}" for currency, rate in RATES.items())


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


TRANSACTIONS = TableContract(
    table="transactions",
    key="transaction_id",
    keep_first_by="try_cast(process_date AS DATE) DESC NULLS LAST",
    columns={
        "transaction_id": "transaction_id",
        "occurred_at": "CAST(transaction_date AS TIMESTAMP)",
        "processed_on": "try_cast(process_date AS DATE)",
        "customer_id": "customer_id",
        "product_id": "product_id",
        "transaction_type": "lower(transaction_type)",
        "category": "nullif(transaction_category, '')",
        "amount": _amount,
        "currency": "currency",
        "amount_usd": (
            "coalesce(try_cast(nullif(amount_usd, '') AS DECIMAL(18, 2)), "
            f"CAST(round({_amount} / CASE currency {_rate_cases} END, 2) AS DECIMAL(18, 2)))"
        ),
        "amount_usd_imputed": "nullif(amount_usd, '') IS NULL",
        "channel": "channel",
        "merchant": "nullif(merchant_name, '')",
        "merchant_category": "nullif(merchant_category, '')",
        "country_code": country_code("transaction_country"),
        "city": "nullif(transaction_city, '')",
        "status": "lower(transaction_status)",
        "response_code": "nullif(response_code, '')",
        "is_fraud": "is_fraud = 'True'",
        "fraud_score": "try_cast(nullif(fraud_score, '') AS DOUBLE)",
        "source_file": "filename",
    },
    rules=(
        Rule("key_present", f"NOT {is_blank('transaction_id')}"),
        Rule("occurred_at_is_a_timestamp", "try_cast(transaction_date AS TIMESTAMP) IS NOT NULL"),
        Rule("amount_is_a_non_negative_number", "try_cast(amount AS DECIMAL(18, 2)) >= 0"),
        Rule("currency_is_known", f"currency IN ({_quoted(tuple(RATES))})"),
        Rule("type_is_known", f"transaction_type IN ({_quoted(TYPES)})"),
        Rule("status_is_known", f"transaction_status IN ({_quoted(STATUSES)})"),
        Rule("country_is_known", known_country("transaction_country")),
        Rule("fraud_label_is_boolean", "is_fraud IN ('True', 'False')"),
        Rule("fraud_score_in_range", f"{is_blank('fraud_score')} OR try_cast(fraud_score AS DOUBLE) BETWEEN 0 AND 100"),
        Rule(
            "usd_amount_matches_usd_charge",
            f"currency <> 'USD' OR {is_blank('amount_usd')} OR "
            "abs(try_cast(amount_usd AS DOUBLE) - try_cast(amount AS DOUBLE)) < 0.01",
        ),
        Rule(
            "purchase_has_merchant",
            f"transaction_type <> 'Purchase' OR NOT {is_blank('merchant_name')}",
            blocking=False,
        ),
    ),
    references=(
        Reference("customer_id", "customers", "customer_id"),
        Reference("product_id", "products", "product_id", also=(("customer_id", "customer_id"),)),
    ),
    metrics={
        "amount_usd_copied_from_usd_amount": f"count(*) FILTER (WHERE {is_blank('amount_usd')} AND currency = 'USD')",
        "amount_usd_imputed_with_fixed_rate": f"count(*) FILTER (WHERE {is_blank('amount_usd')} AND currency <> 'USD')",
        # Each daily file also holds events of the early hours of the next day; the event time is what counts.
        "event_on_day_after_process_date": (
            "count(*) FILTER (WHERE CAST(transaction_date AS DATE) > try_cast(process_date AS DATE))"
        ),
    },
)
