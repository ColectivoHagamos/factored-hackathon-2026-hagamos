"""Interpreter with a Claude model behind the interpreter port (P41): it fills the closed schema and decides nothing.

Only masked text reaches the model, through one forced tool call whose input is the interpretation; a reply that does
not validate is discarded. The interpreter it falls back on stays underneath: it answers when the model fails, takes
longer than the timeout or would pass the spending cap, and a person or a threat it finds always wins (POL-01,
POL-02). Text the gateway flagged as an injection never reaches the model.
"""

import logging
import threading
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from vera.contracts.common import Currency, Language
from vera.contracts.interpretation import Answer, ClaimType, ContactChannel, DeclaredChannel, Interpretation
from vera.llm.rules_adapter import RulesInterpreter
from vera.ports.interpreter import InterpreterPort

PROMPT_VERSION = "interpreter-v4"
PROMPT = (Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8")
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
TOOL = "record_interpretation"
MAX_TOKENS = 400
# US$ per million tokens (input, output), from the team's comparison of providers (2026-10-03). A model missing here
# is charged at the highest known price, so the spending cap errs on the safe side.
PRICES: dict[str, tuple[Decimal, Decimal]] = {
    "claude-haiku-4-5-20251001": (Decimal(1), Decimal(5)),
    "claude-sonnet-5-5": (Decimal(2), Decimal(10)),
}
EXPECTING = {
    "claim": "the reason of the contact (the first message of the case)",
    "choice": "a choice among numbered options",
    "yes_no": "an answer to a yes-or-no question",
    "details": "when the transfer was made and how a third party contacted the customer (a scam, POL-10)",
}
# The open question, so that a short answer can be read; nothing in it is about the customer.
QUESTIONS = {
    "ask_claim": "what happened with the card or the account",
    "choose_charge": "which of the listed charges the customer is asking about",
    "clarify": "VERA showed the receipt of the charge and asked whether the customer recognizes it now",
    "ask_channel": "whether the purchase was made online",
    "ask_card": "whether the customer has the card",
    "sweep": "the numbers of the other listed charges the customer does NOT recognize, «todos» or «ninguno»",
    "confirm_block": "whether to block the card",
    "confirm_register": "whether to register the dispute",
    "confirm_person": "whether the customer wants to be passed to a person",
    "person_offered": "VERA offered to review the case first: yes keeps VERA, no asks for the person",
    "scam_details": "when the transfer was made and how the third party contacted the customer",
    "choose_card": "which of the listed cards the customer lost or had stolen",
    "review": "the numbers of the listed recent movements the customer does NOT recognize, «todos» or «ninguno»",
}

logger = logging.getLogger("vera.llm")


def _enum(values: type[StrEnum], nullable: bool = False) -> dict:
    schema = {"type": "string", "enum": [value.value for value in values]}
    return {"anyOf": [schema, {"type": "null"}]} if nullable else schema


TOOL_DEFINITION = {
    "name": TOOL,
    "description": "Record what the customer's message says, in the closed schema of the bank. It decides nothing.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "claim_type": _enum(ClaimType),
            "amount": {"type": ["number", "null"], "minimum": 0},
            "currency": _enum(Currency, nullable=True),
            "date_text": {"type": ["string", "null"], "maxLength": 200},
            "merchant_text": {"type": ["string", "null"], "maxLength": 200},
            "declared_channel": _enum(DeclaredChannel, nullable=True),
            "has_card": _enum(Answer),
            "authorized_payment": _enum(Answer),
            "contact_channel": _enum(ContactChannel, nullable=True),
            "coercion": {"type": "boolean"},
            "regulator_mentioned": {"type": "boolean"},
            "pix_mentioned": {"type": "boolean"},
            "asks_if_human": {"type": "boolean"},
            "greeting": {"type": "boolean"},
            "answer": _enum(Answer),
            "selected_numbers": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 50}},
            "language": _enum(Language),
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["claim_type", "answer", "language", "confidence"],
    },
}


class MessagesClient(Protocol):
    """The one call of the Anthropic SDK the adapter makes (client.messages), so tests can pass a fake."""

    def create(self, **request: Any) -> Any: ...


class Spending:
    """Calls, fallbacks, tokens and cost since start, with a cap past which every message goes to the fallback."""

    def __init__(self, model: str, cap_usd: Decimal) -> None:
        self._prices = PRICES.get(model, max(PRICES.values()))
        self._cap = cap_usd
        self._lock = threading.Lock()
        self._counts = {"calls": 0, "fallbacks": 0, "input_tokens": 0, "output_tokens": 0}
        self._spent = Decimal(0)

    def allows(self) -> bool:
        with self._lock:
            return self._spent < self._cap

    def charge(self, input_tokens: int, output_tokens: int) -> None:
        price_in, price_out = self._prices
        with self._lock:
            self._counts["calls"] += 1
            self._counts["input_tokens"] += input_tokens
            self._counts["output_tokens"] += output_tokens
            self._spent += (input_tokens * price_in + output_tokens * price_out) / Decimal(1_000_000)

    def fallback(self) -> None:
        with self._lock:
            self._counts["fallbacks"] += 1

    def snapshot(self) -> dict[str, int | float]:
        with self._lock:
            return {**self._counts, "spent_usd": float(round(self._spent, 4)), "cap_usd": float(self._cap)}


class AnthropicInterpreter:
    name = "anthropic"

    def __init__(
        self,
        messages: MessagesClient,
        model: str = DEFAULT_MODEL,
        cap_usd: Decimal = Decimal(15),
        fallback: InterpreterPort | None = None,
    ) -> None:
        self.model = model
        self.prompt_version = PROMPT_VERSION
        self.spending = Spending(model, cap_usd)
        self._messages = messages
        self._fallback = fallback or RulesInterpreter()

    def interpret(self, masked_text: str, context: dict[str, str]) -> Interpretation:
        floor = self._fallback.interpret(masked_text, context)
        if context.get("flagged") or floor.claim_type is ClaimType.HUMAN_REQUEST or floor.coercion:
            return floor
        if not self.spending.allows():
            self.spending.fallback()
            return floor
        try:
            response = self._messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=PROMPT,
                tools=[TOOL_DEFINITION],
                tool_choice={"type": "tool", "name": TOOL},
                messages=[{"role": "user", "content": _request(masked_text, context)}],
            )
        except Exception as error:  # timeouts, rate limits, outages: the fallback answers this message
            return self._fall_back(floor, error)
        self.spending.charge(response.usage.input_tokens, response.usage.output_tokens)
        try:
            fields = next(block.input for block in response.content if block.type == "tool_use")
            reading = Interpretation.model_validate(fields)
        except (StopIteration, ValueError) as error:  # no record, or one outside the closed schema
            return self._fall_back(floor, error)
        return _with_safety_floor(reading, floor)

    def _fall_back(self, floor: Interpretation, error: Exception) -> Interpretation:
        self.spending.fallback()
        # Only the kind of failure is logged: never the message, which is the customer's.
        logger.warning("interpreter fallback: %s", type(error).__name__)
        return floor


def _request(masked_text: str, context: dict[str, str]) -> str:
    lines = [f"Expected from the customer: {EXPECTING.get(context.get('expecting', ''), 'a message')}."]
    if question := QUESTIONS.get(context.get("question", "")):
        lines.append(f"Open question: {question}.")
    lines.append(f"Language of the conversation so far: {context.get('language', 'es')}.")
    return "\n".join([*lines, f"<customer_message>\n{masked_text}\n</customer_message>"])


def _with_safety_floor(reading: Interpretation, floor: Interpretation) -> Interpretation:
    """The model reads; the fallback is a floor for the safety words and for the facts of a scam it left unsaid."""
    authorized = reading.authorized_payment
    return reading.model_copy(
        update={
            # POL-02, POL-09, POL-15: the model can add a safety word, never take one away.
            "coercion": reading.coercion or floor.coercion,
            "regulator_mentioned": reading.regulator_mentioned or floor.regulator_mentioned,
            "pix_mentioned": reading.pix_mentioned or floor.pix_mentioned,
            "asks_if_human": reading.asks_if_human or floor.asks_if_human,
            # A greeting the rules heard is welcomed even when the model reads it as another topic.
            "greeting": reading.greeting or floor.greeting,
            # POL-10: what the customer says about a payment made under deception goes to Fraud, so a fact the rules
            # heard is kept when the model is silent. The purchase channel and the card are left alone: they steer
            # the flow, and there the model's silence is a reason to ask.
            "authorized_payment": floor.authorized_payment if authorized is Answer.NOT_SAID else authorized,
            "date_text": reading.date_text or floor.date_text,
            "contact_channel": reading.contact_channel or floor.contact_channel,
            # POL-06: the model may say the customer lacks the card, which leads to protection, but not that the
            # customer has it unless the words say so: a wrong yes would skip the question and the block offer.
            "has_card": floor.has_card if reading.has_card is Answer.YES else reading.has_card,
        }
    )
