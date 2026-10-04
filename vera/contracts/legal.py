"""Legal rules as loaded from the policy YAML: only executable N1 law rules may yield a date."""

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
    url: HttpUrl


class LegalRule(Contract):
    id: RuleId
    country: Jurisdiction
    route: RouteId
    literal_text: str = Field(min_length=1)
    text_sha256: Sha256Hex
    source: Source
    effective_from: date
    effective_to: date | None = None
    # Policy v1.4 section 5.1: published rules that favor the customer, applied before they are mandatory.
    early_adoption: bool = False
    level: Level
    executable: bool
    layer: Layer
    party: Party | None = None
    term_value: int | None = Field(default=None, ge=0)
    term_unit: TermUnit | None = None
    response_languages: tuple[Language, ...] = (Language.ES, Language.PT)

    @model_validator(mode="after")
    def _only_verified_law_is_executable(self) -> Self:
        # Policy section 16: a changed official text no longer matches its fingerprint and must be reviewed.
        if hashlib.sha256(self.literal_text.encode("utf-8")).hexdigest() != self.text_sha256:
            raise ValueError("text_sha256 does not match literal_text")
        if self.executable and (self.level is not Level.N1 or self.layer is not Layer.LAW):
            raise ValueError("only N1 rules of the law layer can be executable")
        if (self.term_value is None) != (self.term_unit is None) and self.term_unit is not TermUnit.IMMEDIATE:
            raise ValueError("term_value and term_unit go together")
        if self.term_unit is not None and self.party is None:
            raise ValueError("a term needs the party that must act")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot precede effective_from")
        return self
