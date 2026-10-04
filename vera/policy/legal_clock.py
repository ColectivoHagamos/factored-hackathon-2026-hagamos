"""Legal clock: business days per country and due dates that come only from executable rules.

A rule without its verified literal text, out of force on the date of the facts, or whose term starts at a later
event, gives no date: the route is passed on and the reason is stated. The agent never invents a deadline.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import holidays as holiday_calendars
import yaml

from vera.contracts.legal import CountsFrom, LegalRule, Party, RuleStatus, Term, TermUnit

LEGAL_DIR = Path(__file__).with_name("legal")
HOLIDAYS_FILE = Path(__file__).with_name("holidays.yaml")
YEARS = range(2023, 2029)


class BusinessCalendar:
    def __init__(self, country: str, add: Iterable[date] = (), remove: Iterable[date] = ()) -> None:
        library = set(holiday_calendars.country_holidays(country, years=YEARS))
        self.country = country
        self._holidays = frozenset((library | set(add)) - set(remove))

    def is_business_day(self, day: date) -> bool:
        return day.weekday() < 5 and day not in self._holidays

    def add_business_days(self, start: date, count: int) -> date:
        """The day after the start is the first one counted, as legal terms are read."""
        day = start
        while count > 0:
            day += timedelta(days=1)
            if self.is_business_day(day):
                count -= 1
        return day


def load_calendars(path: Path = HOLIDAYS_FILE) -> dict[str, BusinessCalendar]:
    adjustments = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        country: BusinessCalendar(country, entry.get("add") or (), entry.get("remove") or ())
        for country, entry in adjustments.items()
    }


def load_rules(folder: Path = LEGAL_DIR) -> tuple[LegalRule, ...]:
    rules = [
        LegalRule.model_validate(rule)
        for path in sorted(folder.glob("*.yaml"))
        for rule in yaml.safe_load(path.read_text(encoding="utf-8"))["rules"]
    ]
    ids = [rule.id for rule in rules]
    if len(ids) != len(set(ids)):
        raise ValueError("legal rule ids must be unique")
    return tuple(rules)


def status_on(rule: LegalRule, day: date) -> RuleStatus | None:
    """In force by law, early adopted by the bank, or None when the rule does not apply on that day."""
    if rule.effective_to and day > rule.effective_to:
        return None
    if rule.effective_from is None or day >= rule.effective_from:
        return RuleStatus.IN_FORCE_BY_LAW
    return RuleStatus.EARLY_ADOPTED if rule.early_adoption else None


def resolved_unit(term: Term) -> TermUnit:
    """Master policy section 5: unqualified days are business days for the customer and calendar days for the bank."""
    if term.unit is TermUnit.DAYS:
        return TermUnit.BUSINESS_DAYS if term.party is Party.CUSTOMER else TermUnit.CALENDAR_DAYS
    return term.unit


@dataclass(frozen=True)
class Due:
    rule_id: str
    party: Party
    what: str
    unit: TermUnit
    due: date | None
    status: RuleStatus | None
    in_force_from: date | None
    # Why there is no date, when there is none.
    reason: str | None = None


class LegalClock:
    def __init__(self, rules: Iterable[LegalRule], calendars: Mapping[str, BusinessCalendar]) -> None:
        self._rules = {rule.id: rule for rule in rules}
        self._calendars = dict(calendars)

    @classmethod
    def from_files(cls) -> "LegalClock":
        return cls(load_rules(), load_calendars())

    def rule(self, rule_id: str) -> LegalRule:
        return self._rules[rule_id]

    def has(self, rule_id: str) -> bool:
        return rule_id in self._rules

    def rules_for_route(self, route: str) -> tuple[LegalRule, ...]:
        return tuple(rule for rule in self._rules.values() if rule.route == route)

    def deadlines(
        self, rule_id: str, *, event_day: date, filing_day: date, conditions: frozenset[str] = frozenset()
    ) -> tuple[Due, ...]:
        """Due dates of a rule for a fact of event_day claimed on filing_day, which is also the date of the facts."""
        rule = self._rules[rule_id]
        status = status_on(rule, filing_day)
        no_date = _reason_without_date(rule, status)
        terms = _applicable_terms(rule.terms, conditions)
        dues: dict[str, date | None] = {}
        result = []
        for term in terms:
            unit = resolved_unit(term)
            if no_date:
                due, reason = None, no_date
            elif term.counts_from is CountsFrom.LATER:
                due, reason = None, f"starts at a later event: {term.starts_at}"
            else:
                start = dues.get(term.follows) if term.follows else None
                start = start or (event_day if term.counts_from is CountsFrom.EVENT else filing_day)
                due, reason = self._add(rule.country.value, start, term.value, unit), None
            if term.key:
                dues[term.key] = due
            in_force_from = rule.effective_from if status is RuleStatus.EARLY_ADOPTED else None
            result.append(Due(rule.id, term.party, term.what, unit, due, status, in_force_from, reason))
        return tuple(result)

    def _add(self, country: str, start: date, value: int | None, unit: TermUnit) -> date:
        if unit is TermUnit.IMMEDIATE:
            return start
        if unit is TermUnit.BUSINESS_DAYS:
            return self._calendars[country].add_business_days(start, value or 0)
        if unit is TermUnit.HOURS:
            return start + timedelta(hours=value or 0)
        return start + timedelta(days=value or 0)


def _reason_without_date(rule: LegalRule, status: RuleStatus | None) -> str | None:
    if not rule.executable:
        return "the literal text of the rule has not been verified: informed without a date"
    if status is None:
        return "the rule is not in force on the date of the facts"
    return None


def _applicable_terms(terms: Iterable[Term], conditions: frozenset[str]) -> list[Term]:
    """A term with a condition that holds replaces the general term for the same party and duty."""
    terms = list(terms)
    replaced = {
        (term.party, term.what, term.follows) for term in terms if term.applies_when and term.applies_when in conditions
    }
    return [
        term
        for term in terms
        if (term.applies_when in conditions)
        or (term.applies_when is None and (term.party, term.what, term.follows) not in replaced)
    ]
