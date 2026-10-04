"""Daily exchange rates. Kept for the path to production; no demo decision uses them."""

from pipeline.contracts.base import Rule, TableContract

_currencies = "('USD', 'COP', 'ARS', 'MXN')"

EXCHANGE_RATES = TableContract(
    table="daily_exchange_rates",
    key="date || source_currency || target_currency",
    keep_first_by="date",
    columns={
        "rate_date": "CAST(date AS DATE)",
        "source_currency": "source_currency",
        "target_currency": "target_currency",
        "rate": "CAST(exchange_rate AS DOUBLE)",
        "buy_rate": "try_cast(buy_rate AS DOUBLE)",
        "sell_rate": "try_cast(sell_rate AS DOUBLE)",
        "provider": "source",
        "source_file": "filename",
    },
    rules=(
        Rule("date_is_a_date", "try_cast(date AS DATE) IS NOT NULL"),
        Rule("currencies_are_known", f"source_currency IN {_currencies} AND target_currency IN {_currencies}"),
        Rule("rate_is_positive", "try_cast(exchange_rate AS DOUBLE) > 0"),
    ),
)
