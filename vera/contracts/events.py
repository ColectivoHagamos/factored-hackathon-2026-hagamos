"""Append-only event log entries; the conversation state is the reduction of its events."""

from enum import StrEnum

from pydantic import AwareDatetime, JsonValue

from vera.contracts.common import Contract, Identifier, Sha256Hex


class EventType(StrEnum):
    CUSTOMER_MESSAGE = "customer_message"
    INTERPRETATION = "interpretation"
    TOOL_CALLED = "tool_called"
    TOOL_RESULT = "tool_result"
    RULE_DECISION = "rule_decision"
    CONFIRMATION = "confirmation"
    ACTION_READ_BACK = "action_read_back"
    CLARIFICATION_CONFIRMED = "clarification_confirmed"
    REPLY = "reply"
    HANDOFF = "handoff"
    FRAUD_ALERT = "fraud_alert"


class Event(Contract):
    event_id: Identifier
    conversation_id: Identifier
    ts: AwareDatetime
    type: EventType
    data: dict[str, JsonValue]
    llm_provider: Identifier | None = None
    # None only for the first event of a conversation.
    prev_hash: Sha256Hex | None
    hash: Sha256Hex
