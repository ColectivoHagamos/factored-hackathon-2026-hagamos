"""Closed schema returned by the interpreter for each customer message."""

from enum import StrEnum
from typing import Annotated

from pydantic import Field

from vera.contracts.common import Amount, Contract, Currency, Language, ShortText


class ClaimType(StrEnum):
    UNRECOGNIZED_CHARGE = "unrecognized_charge"
    IMPROPER_CHARGE = "improper_charge"
    SCAM_TRANSFER = "scam_transfer"
    HUMAN_REQUEST = "human_request"
    OUT_OF_SCOPE = "out_of_scope"


class DeclaredChannel(StrEnum):
    """Purchase channel as stated by the customer; the dataset channel is random and never used."""

    ONLINE = "online"
    IN_PERSON = "in_person"
    UNKNOWN = "unknown"


class ContactChannel(StrEnum):
    """How a third party reached the customer before a payment made under deception, as the customer says (POL-10)."""

    PHONE_CALL = "phone_call"
    MESSAGE = "message"
    EMAIL = "email"
    SOCIAL_MEDIA = "social_media"
    WEBSITE = "website"
    IN_PERSON = "in_person"


class Answer(StrEnum):
    """Answer to a yes-or-no question that keeps the case in which the customer did not say."""

    YES = "yes"
    NO = "no"
    NOT_SAID = "not_said"


class Interpretation(Contract):
    """Fields extracted from one masked message; anything outside this schema is discarded."""

    claim_type: ClaimType
    amount: Amount | None = None
    currency: Currency | None = None
    # What the customer said; the actual date is computed by code, never by the model.
    date_text: ShortText | None = None
    merchant_text: ShortText | None = None
    declared_channel: DeclaredChannel | None = None
    has_card: Answer = Answer.NOT_SAID
    authorized_payment: Answer = Answer.NOT_SAID
    contact_channel: ContactChannel | None = None
    coercion: bool = False
    regulator_mentioned: bool = False
    pix_mentioned: bool = False
    # "¿Eres una persona?": a question about VERA, not a request for a person.
    asks_if_human: bool = False
    # A greeting, thanks, small talk, a question about what VERA does, or a plea for help that says nothing yet.
    greeting: bool = False
    # Worry, fear, anger or frustration in the customer's words: VERA validates the emotion before going on.
    distress: bool = False
    # Answer to the yes-or-no question asked in the previous turn, and option numbers the customer referred to.
    answer: Answer = Answer.NOT_SAID
    selected_numbers: tuple[Annotated[int, Field(ge=1, le=50)], ...] = ()
    language: Language
    # POL-14: below the calibrated threshold the agent asks instead of acting.
    confidence: float = Field(ge=0, le=1)
