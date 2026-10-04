"""Legal rules as loaded from YAML: only an N1 rule of the law layer, with its verified literal text, yields a date."""

import hashlib
from datetime import date
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, HttpUrl, StringConstraints, model_validator

from vera.contracts.common import Contract, Language, Sha256Hex, ShortText

RuleId = Annotated[str, StringConstraints(pattern=r"^(CO|MX|AR|BR)-R\d{2}$")]
RouteId = Annotated[str, StringConstraints(pattern=r"^(CO|MX|AR|BR)-[a-z0-9]+(-[a-z0-9]+)*$")]


class Jurisdiction(StrEnum):
    MX = "MX"
    CO = "CO"
    AR = "AR"
    BR = "BR"


class Level(StrEnum):
    """Verification level: N1 read in the official source, N2 official reference, N3 pending."""

    N1 = "N1"
    N2 = "N2"
    N3 = "N3"


class Layer(StrEnum):
    """Origin of a rule; contractual network rules are never presented as law."""

    LAW = "law"
    NETWORK = "network"
    BANK = "bank"


class TermUnit(StrEnum):
    HOURS = "hours"
    # "Days" without qualification; the master policy reads them as business days for the customer and
    # calendar days for the bank, the reading that favors the customer in both cases.
    DAYS = "days"
    CALENDAR_DAYS = "calendar_days"
    BUSINESS_DAYS = "business_days"
    IMMEDIATE = "immediate"


class Party(StrEnum):
    BANK = "bank"
    CUSTOMER = "customer"


class RuleStatus(StrEnum):
    """Status of an applicable rule on the date of the facts."""

    IN_FORCE_BY_LAW = "in_force_by_law"
    EARLY_ADOPTED = "early_adopted"


class Source(Contract):
    title: ShortText
    provision: ShortText
    url: HttpUrl


class CountsFrom(StrEnum):
    """When a term starts: the fact (customer windows), the filing of the claim, or a later event."""

    EVENT = "event"
    FILING = "filing"
    LATER = "later"


class Term(Contract):
    party: Party
    what: ShortText
    value: int | None = Field(default=None, ge=0)
    unit: TermUnit
    # Event that starts the count, as the text states it, and how the clock reads it.
    starts_at: ShortText
    counts_from: CountsFrom
    # Short name of the term, so that a later term can follow it ("within the 15 days following").
    key: ShortText | None = None
    follows: ShortText | None = None
    # Condition under which this term replaces the general one, for example "charge_abroad".
    applies_when: ShortText | None = None

    @model_validator(mode="after")
    def _value_matches_unit(self) -> Self:
        if (self.unit is TermUnit.IMMEDIATE) != (self.value is None):
            raise ValueError("only an immediate term has no value")
        return self


class LegalRule(Contract):
    id: RuleId
    country: Jurisdiction
    route: RouteId
    summary: ShortText
    source: Source
    # Exact official text and its SHA-256; empty while the text has not been loaded from the official source.
    literal_text: str | None = Field(default=None, min_length=1)
    text_sha256: Sha256Hex | None = None
    # Left empty when the date has not been checked: the repository never infers dates.
    effective_from: date | None = None
    effective_to: date | None = None
    # Policy v1.4 section 5.1: published rules that favor the customer, applied before they are mandatory.
    early_adoption: bool = False
    level: Level
    executable: bool
    layer: Layer
    terms: tuple[Term, ...] = ()
    response_languages: tuple[Language, ...] = (Language.ES, Language.PT)
    checked_on: date | None = None
    legal_review: bool = False

    @model_validator(mode="after")
    def _only_verified_law_is_executable(self) -> Self:
        if (self.literal_text is None) != (self.text_sha256 is None):
            raise ValueError("literal_text and text_sha256 go together")
        # Policy section 16: a changed official text no longer matches its fingerprint and must be reviewed.
        if self.literal_text and hashlib.sha256(self.literal_text.encode("utf-8")).hexdigest() != self.text_sha256:
            raise ValueError("text_sha256 does not match literal_text")
        if self.executable and (self.level is not Level.N1 or self.layer is not Layer.LAW or not self.literal_text):
            raise ValueError("only N1 rules of the law layer with their literal text can be executable")
        keys = [term.key for term in self.terms if term.key]
        if any(term.follows and term.follows not in keys for term in self.terms):
            raise ValueError("a term can only follow another term of the same rule")
        if self.early_adoption and self.effective_from is None:
            raise ValueError("an early adopted rule needs the date it becomes mandatory")
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot precede effective_from")
        return self
