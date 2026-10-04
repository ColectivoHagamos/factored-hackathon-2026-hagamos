"""Legal route of a dispute by the country of the account, with the dates the legal clock can verify.

With these routes every customer in Mexico, Colombia and Argentina has a way to reach the bank (policy section 10).
A route whose rule has no verified text is recorded and passed on without a date.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from vera.contracts.cases import DisputeReason
from vera.contracts.common import Country
from vera.contracts.interpretation import DeclaredChannel
from vera.policy.legal_clock import Due, LegalClock

NETWORK_TERM_DAYS = 120


@dataclass(frozen=True)
class RouteStep:
    route: str
    name: dict[str, str]
    rule_ids: tuple[str, ...]


@dataclass(frozen=True)
class LegalAssessment:
    route: str
    rules: tuple[str, ...]
    dues: tuple[Due, ...]
    venues: tuple[str, ...]
    without_date: tuple[RouteStep, ...]

    @property
    def deadline_verified(self) -> bool:
        return any(due.due is not None for due in self.dues)


REVERSAL_CO = RouteStep(
    "CO-payment-reversal",
    {"es": "Reversión del pago (Decreto 587)", "pt": "Reversão do pagamento (Decreto 587)"},
    ("CO-R01",),
)
COMPLAINT_CO = RouteStep("CO-bank-complaint", {"es": "Reclamo ante el banco", "pt": "Reclamação ao banco"}, ("CO-R15",))
CLARIFICATION_MX = RouteStep(
    "MX-clarification",
    {"es": "Aclaración (LTOSF, art. 23)", "pt": "Esclarecimento (LTOSF, art. 23)"},
    ("MX-R01", "MX-R03"),
)
CHALLENGE_AR = RouteStep(
    "AR-statement-challenge",
    {"es": "Impugnación del resumen (Ley 25.065)", "pt": "Contestação da fatura (Lei 25.065)"},
    ("AR-R05",),
)
COMPLAINT_AR = RouteStep("AR-bank-complaint", {"es": "Reclamo ante el banco", "pt": "Reclamação ao banco"}, ("AR-R03",))
VENUES = {
    Country.CO: ("bank", "SFC (jurisdictional route)"),
    Country.MX: ("bank specialized unit (UNE)", "CONDUSEF"),
    Country.AR: ("bank", "BCRA"),
}


def routes_for(
    country: Country, channel: DeclaredChannel | None, charge_country: str | None, card_type: str | None
) -> tuple[RouteStep, ...]:
    if country is Country.CO:
        domestic_online = channel is DeclaredChannel.ONLINE and charge_country == "CO"
        return (REVERSAL_CO, COMPLAINT_CO) if domestic_online else (COMPLAINT_CO,)
    if country is Country.MX:
        return (CLARIFICATION_MX,)
    return (CHALLENGE_AR, COMPLAINT_AR) if card_type == "credit" else (COMPLAINT_AR,)


def assess(
    clock: LegalClock,
    country: Country,
    channel: DeclaredChannel | None,
    charge_country: str | None,
    card_type: str | None,
    event_day: date,
    filing_day: date,
) -> LegalAssessment:
    """Routes in order of preference, the dates of their executable rules and the steps that stay without a date."""
    steps = routes_for(country, channel, charge_country, card_type)
    conditions = frozenset({"charge_abroad"}) if charge_country and charge_country != country.value else frozenset()
    dues: list[Due] = []
    without_date: list[RouteStep] = []
    for step in steps:
        loaded = [rule_id for rule_id in step.rule_ids if clock.has(rule_id)]
        step_dues = [
            due
            for rule_id in loaded
            for due in clock.deadlines(rule_id, event_day=event_day, filing_day=filing_day, conditions=conditions)
        ]
        dues.extend(step_dues)
        if not any(due.due for due in step_dues):
            without_date.append(step)
    dated = next((step for step in steps if step not in without_date), steps[-1])
    rules = tuple(rule_id for step in steps for rule_id in step.rule_ids)
    return LegalAssessment(dated.route, rules, tuple(dues), VENUES[country], tuple(without_date))


def network_code(reason: DisputeReason, channel: DeclaredChannel | None) -> str:
    """Card network reason code suggested to the analyst; the analyst confirms it."""
    if reason is DisputeReason.FRAUD:
        return "10.3" if channel is DeclaredChannel.IN_PERSON else "10.4"
    return {
        DisputeReason.NOT_RECEIVED: "13.1",
        DisputeReason.NOT_AS_DESCRIBED: "13.3",
        DisputeReason.INCORRECT_AMOUNT: "12.5",
        DisputeReason.DUPLICATE: "12.6.1",
        DisputeReason.CANCELLED_RECURRING: "13.2",
    }.get(reason, "10.4")


def network_due(occurred_at: datetime) -> date:
    return (occurred_at + timedelta(days=NETWORK_TERM_DAYS)).date()
