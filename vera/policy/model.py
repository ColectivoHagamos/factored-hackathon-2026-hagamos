"""Executable policy loaded from YAML: version, parameters and the text of each rule."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Self

import yaml
from pydantic import Field, StringConstraints, model_validator

from vera.contracts.common import Contract, Currency

DEFAULT_POLICY = Path(__file__).with_name("policy_v1.yaml")

PolicyId = Annotated[str, StringConstraints(pattern=r"^POL-\d{2}$")]
ProhibitionId = Annotated[str, StringConstraints(pattern=r"^PROH-\d{2}$")]


class Parameters(Contract):
    exposure_threshold_usd: Decimal = Field(gt=0)
    fraud_score_threshold: int = Field(ge=0, le=100)
    unrecognized_charges_signal: int = Field(ge=1)
    repeat_disputes: int = Field(ge=1)
    repeat_window_days: int = Field(ge=1)
    interpreter_min_confidence: float = Field(gt=0, lt=1)
    max_question_attempts: int = Field(ge=1)
    offers_before_transfer: int = Field(ge=0)
    system_clock: date
    network_term_days: int = Field(ge=1)
    goodwill_max_usd: Decimal = Field(gt=0)
    goodwill_window_days: int = Field(ge=1)
    usd_rates: dict[Currency, Decimal]

    @model_validator(mode="after")
    def _every_currency_has_a_rate(self) -> Self:
        if set(self.usd_rates) != set(Currency) or self.usd_rates[Currency.USD] != 1:
            raise ValueError("usd_rates needs every currency, with USD equal to 1")
        return self


class RuleText(Contract):
    id: PolicyId
    when: str = Field(min_length=1)
    then: str = Field(min_length=1)


class Prohibition(Contract):
    id: ProhibitionId
    text: str = Field(min_length=1)
    enforced_by: str = Field(min_length=1)


class Policy(Contract):
    version: Annotated[str, StringConstraints(pattern=r"^\d+\.\d+$")]
    effective_from: date
    parameters: Parameters
    rules: tuple[RuleText, ...]
    prohibitions: tuple[Prohibition, ...]

    @model_validator(mode="after")
    def _ids_are_unique(self) -> Self:
        ids = [rule.id for rule in self.rules] + [prohibition.id for prohibition in self.prohibitions]
        if len(ids) != len(set(ids)):
            raise ValueError("rule and prohibition ids must be unique")
        return self

    @property
    def ids(self) -> frozenset[str]:
        return frozenset(rule.id for rule in self.rules) | {prohibition.id for prohibition in self.prohibitions}


def load_policy(path: Path = DEFAULT_POLICY) -> Policy:
    """Load and validate the policy; a malformed file stops the start-up."""
    return Policy.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
