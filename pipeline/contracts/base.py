"""Building blocks of a table contract. Checks are SQL expressions over the raw text columns of bronze."""

from dataclasses import dataclass, field

# Country names as they appear in the dataset, including spelling variants, mapped to ISO 3166 codes.
COUNTRY_CODES = {
    "México": "MX",
    "Mexico": "MX",
    "Colombia": "CO",
    "Argentina": "AR",
    "USA": "US",
    "Spain": "ES",
    "Brazil": "BR",
}


def country_code(column: str) -> str:
    """SQL expression that maps a country name of the dataset to its ISO code."""
    cases = " ".join(f"WHEN '{name}' THEN '{code}'" for name, code in COUNTRY_CODES.items())
    return f"CASE {column} {cases} END"


def known_country(column: str) -> str:
    names = ", ".join(f"'{name}'" for name in COUNTRY_CODES)
    return f"{column} IN ({names})"


def is_blank(column: str) -> str:
    return f"coalesce(trim({column}), '') = ''"


@dataclass(frozen=True)
class Rule:
    """A named check; a row that fails a blocking rule goes to quarantine with the rule name as its reason."""

    name: str
    check: str
    blocking: bool = True


@dataclass(frozen=True)
class Reference:
    """Foreign key to a table that is already in silver."""

    column: str
    table: str
    key: str
    # Extra equality conditions, for example the product must belong to the same customer.
    also: tuple[tuple[str, str], ...] = ()

    @property
    def name(self) -> str:
        return f"orphan_{self.column}"


@dataclass(frozen=True)
class TableContract:
    table: str
    key: str
    # When a key repeats, the first row in this order is kept and the others are quarantined.
    keep_first_by: str
    columns: dict[str, str]
    rules: tuple[Rule, ...]
    references: tuple[Reference, ...] = field(default=())
    # Aggregates over the rows that reach silver, reported as metrics (for example imputed values).
    metrics: dict[str, str] = field(default_factory=dict)

    @property
    def blocking_rules(self) -> tuple[Rule, ...]:
        return tuple(rule for rule in self.rules if rule.blocking)

    @property
    def warning_rules(self) -> tuple[Rule, ...]:
        return tuple(rule for rule in self.rules if not rule.blocking)
