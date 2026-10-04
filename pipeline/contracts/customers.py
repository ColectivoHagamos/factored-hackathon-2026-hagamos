"""Customers. Data minimization: names, documents, contact data and addresses do not reach silver."""

from pipeline.contracts.base import Rule, TableContract, country_code, is_blank, known_country

CUSTOMERS = TableContract(
    table="customers",
    key="customer_id",
    keep_first_by="try_cast(last_updated AS TIMESTAMP) DESC NULLS LAST",
    columns={
        "customer_id": "customer_id",
        "country_code": country_code("country"),
        "segment": "lower(segment)",
        "customer_status": "lower(customer_status)",
        "detected_accent": "nullif(detected_accent, '')",
        "birth_year": "year(CAST(date_of_birth AS DATE))",
        "registered_at": "CAST(registration_date AS TIMESTAMP)",
        "source_file": "filename",
    },
    rules=(
        Rule("key_present", f"NOT {is_blank('customer_id')}"),
        Rule("country_is_known", known_country("country")),
        Rule("segment_is_known", "segment IN ('Basic', 'Plus', 'Premium', 'Student')"),
        Rule("status_is_known", "customer_status IN ('Active', 'Inactive', 'Suspended', 'Closed')"),
        Rule("birth_date_is_a_date", "try_cast(date_of_birth AS DATE) IS NOT NULL"),
        Rule("registration_is_a_timestamp", "try_cast(registration_date AS TIMESTAMP) IS NOT NULL"),
    ),
)
