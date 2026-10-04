"""Shared value types for every boundary model."""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class Contract(BaseModel):
    """Base for boundary models: unknown fields are rejected and instances are immutable."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Country(StrEnum):
    MX = "MX"
    CO = "CO"
    AR = "AR"


class Currency(StrEnum):
    """Currencies present in the dataset; Mexico operates in USD only."""

    USD = "USD"
    COP = "COP"
    ARS = "ARS"


class Language(StrEnum):
    ES = "es"
    PT = "pt"


Amount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]
CandidateNumber = Annotated[int, Field(ge=1, le=50)]
CaseId = Annotated[str, StringConstraints(pattern=r"^DSP-\d{6}$")]
MaskedCard = Annotated[str, StringConstraints(pattern=r"^•••• \d{4}$")]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
ShortText = Annotated[str, StringConstraints(min_length=1, max_length=200)]
Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$")]


class Money(Contract):
    amount: Amount
    currency: Currency
