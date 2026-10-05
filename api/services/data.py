"""The data behind the demo, for a reviewer: the tables of the Factored dataset the pipeline read, and the
pseudonymized subset VERA runs on, counted live through the ports. Only totals leave this module, never a record."""

import json
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from api.schemas import Count, DataOverview, DemoSubset, SourceTable
from vera.ports.bank import CardsPort, CustomersPort, TransactionsPort

# The reports the pipeline writes when it builds the data; the image carries them next to the code.
REPORTS = Path(__file__).resolve().parents[2] / "docs"
# Every movement of the subset: it holds the last 180 days up to the demo's clock, and its disputes the last year.
SINCE = datetime(2000, 1, 1)


def _counts(counter: Counter) -> tuple[Count, ...]:
    return tuple(Count(label=label, count=count) for label, count in sorted(counter.items()))


class DataOverviewService:
    def __init__(
        self,
        *,
        customers: CustomersPort,
        cards: CardsPort,
        transactions: TransactionsPort,
        now: Callable[[], datetime],
        reports: Path = REPORTS,
    ) -> None:
        self._customers = customers
        self._cards = cards
        self._transactions = transactions
        self._now = now
        self._reports = reports

    def overview(self) -> DataOverview:
        quality = self._read("data_quality_report.json")
        tables = tuple(
            SourceTable(
                name=name,
                rows_in=table["rows_in"],
                rows_valid=table["rows_valid"],
                rows_quarantined=table["rows_quarantined"],
            )
            for name, table in quality.get("tables", {}).items()
        )
        return DataOverview(source_tables=tables, source_manifest=quality.get("bronze_manifest"), subset=self._subset())

    def _subset(self) -> DemoSubset:
        customers = self._customers.customers()
        until = self._now()
        cards, movements, disputes = [], [], 0
        for customer in customers:
            cards += self._cards.cards(customer.customer_ref)
            movements += self._transactions.charges(customer.customer_ref, SINCE, until)
            disputes += self._transactions.disputes_since(customer.customer_ref, SINCE)
        dates = sorted(movement.occurred_at.date() for movement in movements)
        scenarios = self._read("demo_subset_report.json").get("customers_per_scenario", {})
        return DemoSubset(
            customers=len(customers),
            customers_by_country=_counts(Counter(customer.country.value for customer in customers)),
            cards=len(cards),
            cards_by_status=_counts(Counter(card.status for card in cards)),
            movements=len(movements),
            movements_by_kind=_counts(Counter(movement.kind.value for movement in movements)),
            movements_by_status=_counts(Counter(movement.status.value for movement in movements)),
            earlier_disputes=disputes,
            first_movement=dates[0] if dates else None,
            last_movement=dates[-1] if dates else None,
            customers_per_scenario=_counts(Counter(scenarios)),
        )

    def _read(self, name: str) -> dict:
        path = self._reports / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
