"""Mock bank with generated data: one customer per acceptance scenario. Used by CI and by the demo without data.

Every value is invented by the team; nothing comes from the dataset.
"""

from collections.abc import Iterable
from datetime import datetime, timedelta
from decimal import Decimal

from vera.adapters.sqlite_state import SqliteState
from vera.contracts.charges import ChargeKind, ChargeStatus, FraudScoreBand
from vera.contracts.common import Country, Currency
from vera.ports.bank import CardRecord, ChargeRecord, CustomerRecord

CLOCK = datetime(2026, 6, 18, 9, 0)
RATES = {Currency.USD: Decimal(1), Currency.COP: Decimal(4000), Currency.ARS: Decimal(350)}

CUSTOMERS = (
    CustomerRecord("CUS-MOCK00000000001", "CO-01 · plus", Country.CO, "plus", "30-44", ("A1", "A7", "A8")),
    CustomerRecord("CUS-MOCK00000000002", "CO-02 · basic", Country.CO, "basic", "60+", ("A2", "A3", "A6", "A9")),
    CustomerRecord("CUS-MOCK00000000003", "MX-01 · premium", Country.MX, "premium", "45-59", ("A4",)),
    CustomerRecord("CUS-MOCK00000000004", "AR-01 · basic", Country.AR, "basic", "18-29", ("A5",)),
    CustomerRecord("CUS-MOCK00000000005", "MX-02 · student", Country.MX, "student", "18-29", ("A10",)),
)

CARDS = (
    CardRecord("PRD-MOCK00000000011", "CUS-MOCK00000000001", "credit", "•••• 4821", "active"),
    CardRecord("PRD-MOCK00000000021", "CUS-MOCK00000000002", "debit", "•••• 7310", "active"),
    CardRecord("PRD-MOCK00000000031", "CUS-MOCK00000000003", "credit", "•••• 0954", "active"),
    CardRecord("PRD-MOCK00000000041", "CUS-MOCK00000000004", "credit", "•••• 6627", "active"),
    CardRecord("PRD-MOCK00000000051", "CUS-MOCK00000000005", "debit", "•••• 3108", "active"),
)


def _charge(
    n: int,
    customer: int,
    days_ago: float,
    amount: str,
    currency: Currency,
    merchant: str | None,
    city: str,
    country: str,
    status: ChargeStatus = ChargeStatus.APPROVED,
    band: FraudScoreBand = FraudScoreBand.AT_MOST_30,
    kind: ChargeKind = ChargeKind.PURCHASE,
    known: bool = False,
    category: str | None = "Food",
) -> ChargeRecord:
    value = Decimal(amount)
    return ChargeRecord(
        charge_ref=f"TRX-MOCK{n:011d}",
        customer_ref=f"CUS-MOCK{customer:011d}",
        card_ref=f"PRD-MOCK{customer * 10 + 1:011d}" if kind is ChargeKind.PURCHASE else None,
        kind=kind,
        occurred_at=CLOCK - timedelta(days=days_ago),
        amount=value,
        currency=currency,
        amount_usd=(value / RATES[currency]).quantize(Decimal("0.01")),
        merchant=merchant,
        merchant_category=category if merchant else None,
        city=city,
        country_code=country,
        status=status,
        fraud_score_band=band,
        is_known_merchant=known,
    )


CHARGES = (
    # CO-01: recent domestic online purchase (A1) and a known merchant.
    _charge(1, 1, 3.2, "185000", Currency.COP, "Libreria Andina", "Bogota", "CO", category="Services"),
    _charge(2, 1, 1.5, "42000", Currency.COP, "Cafe del Parque", "Bogota", "CO", known=True),
    # CO-02: two rides in Sao Paulo with a high score (A3, A6) and two charges at the same merchant (A9).
    _charge(
        3, 2, 4.1, "120000", Currency.COP, "Uber", "São Paulo", "BR", band=FraudScoreBand.ABOVE_30, category="Transport"
    ),
    _charge(4, 2, 3.8, "65000", Currency.COP, "Uber", "São Paulo", "BR", category="Transport"),
    _charge(5, 2, 2.0, "30000", Currency.COP, "Farmacia Salud", "Medellin", "CO", status=ChargeStatus.PENDING),
    # MX-01: purchase in Madrid in USD (A4).
    _charge(6, 3, 12.0, "240.00", Currency.USD, "Hotel Prado", "Madrid", "ES", category="Services"),
    _charge(7, 3, 6.0, "35.50", Currency.USD, "Super Norte", "Monterrey", "MX", known=True),
    # AR-01: credit card purchase (A5) and a declined attempt.
    _charge(8, 4, 5.0, "45000", Currency.ARS, "Electro Sur", "Rosario", "AR", category="Other"),
    _charge(9, 4, 0.5, "90000", Currency.ARS, "Electro Sur", "Rosario", "AR", status=ChargeStatus.DECLINED),
    # MX-02: bank adjustment (A10) and a reversed purchase.
    _charge(10, 5, 9.0, "18.00", Currency.USD, None, "Puebla", "MX", kind=ChargeKind.BANK_ADJUSTMENT, category=None),
    _charge(11, 5, 7.0, "22.00", Currency.USD, "Cine Centro", "Puebla", "MX", status=ChargeStatus.REVERSED),
)


class MockBank:
    def __init__(self, state: SqliteState, charges: Iterable[ChargeRecord] = CHARGES) -> None:
        self._state = state
        self._charges = tuple(charges)

    def customer(self, customer_ref: str) -> CustomerRecord | None:
        return next((c for c in CUSTOMERS if c.customer_ref == customer_ref), None)

    def customers(self) -> tuple[CustomerRecord, ...]:
        return CUSTOMERS

    def charges(self, customer_ref: str, since: datetime, until: datetime) -> tuple[ChargeRecord, ...]:
        found = (c for c in self._charges if c.customer_ref == customer_ref and since <= c.occurred_at <= until)
        return tuple(sorted(found, key=lambda charge: charge.occurred_at))

    def disputes_since(self, customer_ref: str, since: datetime) -> int:
        return 0

    def cards(self, customer_ref: str) -> tuple[CardRecord, ...]:
        blocked = self._state.blocked_cards()
        return tuple(
            CardRecord(
                c.card_ref, c.customer_ref, c.card_type, c.masked_card, "blocked" if c.card_ref in blocked else c.status
            )
            for c in CARDS
            if c.customer_ref == customer_ref
        )

    def block(self, card_ref: str, idempotency_key: str) -> None:
        self._state.record_block(card_ref, idempotency_key)
