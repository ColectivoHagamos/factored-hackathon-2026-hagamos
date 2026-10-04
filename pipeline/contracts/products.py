"""Products. Card numbers are reduced to their last four digits; the full number never reaches silver."""

from pipeline.contracts.base import Reference, Rule, TableContract, is_blank

PRODUCT_TYPES = {
    "Cuenta Ahorro": "savings_account",
    "Cuenta Corriente": "checking_account",
    "Tarjeta Crédito": "credit_card",
    "Tarjeta Débito": "debit_card",
    "Préstamo Personal": "personal_loan",
    "Préstamo Hipotecario": "mortgage",
    "Inversión": "investment",
    "Seguro": "insurance",
}
CARD_TYPES = ("Tarjeta Crédito", "Tarjeta Débito")

_type_cases = " ".join(f"WHEN '{name}' THEN '{code}'" for name, code in PRODUCT_TYPES.items())
_type_names = ", ".join(f"'{name}'" for name in PRODUCT_TYPES)
_card_names = ", ".join(f"'{name}'" for name in CARD_TYPES)

PRODUCTS = TableContract(
    table="products",
    key="product_id",
    keep_first_by="try_cast(last_updated AS TIMESTAMP) DESC NULLS LAST",
    columns={
        "product_id": "product_id",
        "customer_id": "customer_id",
        "product_type": f"CASE product_type {_type_cases} END",
        "card_last4": f"CASE WHEN product_type IN ({_card_names}) THEN right(product_number, 4) END",
        "currency": "currency",
        "status": "lower(product_status)",
        "opened_on": "CAST(opening_date AS DATE)",
        "expires_on": "try_cast(nullif(expiration_date, '') AS DATE)",
        "source_file": "filename",
    },
    rules=(
        Rule("key_present", f"NOT {is_blank('product_id')}"),
        Rule("type_is_known", f"product_type IN ({_type_names})"),
        Rule("currency_is_known", "currency IN ('USD', 'COP', 'ARS')"),
        Rule("status_is_known", "product_status IN ('Active', 'Closed', 'Blocked', 'Suspended')"),
        Rule("opening_is_a_date", "try_cast(opening_date AS DATE) IS NOT NULL"),
        Rule(
            "card_number_has_16_digits",
            f"product_type NOT IN ({_card_names}) OR regexp_full_match(product_number, '[0-9]{{16}}')",
        ),
    ),
    references=(Reference("customer_id", "customers", "customer_id"),),
)
