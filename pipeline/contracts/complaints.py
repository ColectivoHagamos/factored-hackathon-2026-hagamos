"""Complaints. Only the structured fields reach silver; the free-text description does not."""

from pipeline.contracts.base import Reference, Rule, TableContract, is_blank

SUBCATEGORIES = {
    "Cargo no reconocido": "unrecognized_charge",
    "Cobro indebido": "improper_charge",
    "Problema con app": "app_issue",
    "Atención en sucursal": "branch_service",
    "Calidad de servicio": "service_quality",
}

_cases = " ".join(f"WHEN '{name}' THEN '{code}'" for name, code in SUBCATEGORIES.items())
_names = ", ".join(f"'{name}'" for name in SUBCATEGORIES)

COMPLAINTS = TableContract(
    table="complaints",
    key="complaint_id",
    keep_first_by="try_cast(process_date AS DATE) DESC NULLS LAST",
    columns={
        "complaint_id": "complaint_id",
        "created_at": "CAST(creation_date AS TIMESTAMP)",
        "customer_id": "customer_id",
        "case_type": "lower(case_type)",
        "category": "lower(category)",
        "subcategory": f"CASE subcategory {_cases} END",
        "status": "lower(status)",
        "priority": "lower(priority)",
        "claimed_amount": "try_cast(nullif(claimed_amount, '') AS DECIMAL(18, 2))",
        "currency": "nullif(currency, '')",
        "sla_breached": "sla_breached = 'True'",
        "is_repeat_complainer": "is_repeat_complainer = 'True'",
        "source_file": "filename",
    },
    rules=(
        Rule("key_present", f"NOT {is_blank('complaint_id')}"),
        Rule("created_at_is_a_timestamp", "try_cast(creation_date AS TIMESTAMP) IS NOT NULL"),
        Rule("subcategory_is_known", f"{is_blank('subcategory')} OR subcategory IN ({_names})"),
        Rule(
            "status_is_known",
            "status IN ('Open', 'In Process', 'Escalated', 'Resolved', 'Closed', 'Rejected')",
        ),
        Rule(
            "claimed_amount_is_non_negative", f"{is_blank('claimed_amount')} OR try_cast(claimed_amount AS DOUBLE) >= 0"
        ),
        # MXN appears in complaints although no transaction is in MXN: reported, not quarantined.
        Rule(
            "currency_used_by_transactions",
            f"{is_blank('currency')} OR currency IN ('USD', 'COP', 'ARS')",
            blocking=False,
        ),
    ),
    references=(Reference("customer_id", "customers", "customer_id"),),
)
