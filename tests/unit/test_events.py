"""Tests of the hash-chained events and the conversation reducer (P11)."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from itertools import count

import pytest

from vera.contracts.events import Event, EventType
from vera.core.events import ChainBrokenError, event_hash, new_event, reduce, verify_chain

CONVERSATION = "conv-1"


class Factory:
    """Deterministic clock and identifiers for building conversations."""

    def __init__(self) -> None:
        self._ids: Iterator[int] = count(1)
        self._start = datetime(2026, 6, 18, 15, 0, tzinfo=UTC)
        self.events: list[Event] = []

    def add(self, event_type: EventType, data: dict | None = None, conversation_id: str = CONVERSATION) -> Event:
        n = next(self._ids)
        event = new_event(
            self.events[-1] if self.events else None,
            conversation_id,
            event_type,
            data or {},
            now=lambda: self._start + timedelta(seconds=n),
            new_id=lambda: f"evt-{n}",
        )
        self.events.append(event)
        return event


@pytest.fixture
def conversation() -> list[Event]:
    f = Factory()
    f.add(EventType.CUSTOMER_MESSAGE, {"text": "No reconozco un cargo de Uber"})
    f.add(EventType.INTERPRETATION, {"language": "pt", "claim_type": "unrecognized_charge", "confidence": 0.9})
    f.add(EventType.RULE_DECISION, {"rule": "POL-06", "version": "1.4", "result": "escalate"})
    f.add(EventType.TOOL_CALLED, {"tool": "block_card", "idempotency_key": "blk-1"})
    f.add(EventType.TOOL_RESULT, {"tool": "block_card", "status": "blocked"})
    f.add(EventType.ACTION_READ_BACK, {"idempotency_key": "blk-1", "matches": True})
    f.add(EventType.HANDOFF, {"queue": "fraud"})
    return f.events


def test_a_conversation_is_reproduced_from_its_events(conversation: list[Event]):
    verify_chain(conversation)
    state = reduce(CONVERSATION, conversation)
    assert state.customer_turns == 1
    assert state.language == "pt"
    assert state.rules_applied == ("POL-06",)
    assert state.action_status("blk-1") == "completed"
    assert state.escalated
    assert state.last_hash == conversation[-1].hash
    assert reduce(CONVERSATION, conversation) == state


def test_altering_an_event_breaks_the_chain(conversation: list[Event]):
    tampered = conversation[2].model_copy(update={"data": {"rule": "POL-06", "version": "1.4", "result": "allow"}})
    with pytest.raises(ChainBrokenError) as error:
        verify_chain([*conversation[:2], tampered, *conversation[3:]])
    assert error.value.position == 2


def test_rehashing_an_altered_event_still_breaks_the_next_link(conversation: list[Event]):
    tampered = conversation[2].model_copy(update={"data": {"rule": "POL-06", "result": "allow"}})
    tampered = tampered.model_copy(update={"hash": event_hash(tampered)})
    with pytest.raises(ChainBrokenError) as error:
        verify_chain([*conversation[:2], tampered, *conversation[3:]])
    assert error.value.position == 3


@pytest.mark.parametrize(
    "mutate",
    [lambda e: [e[1], e[0], *e[2:]], lambda e: e[1:], lambda e: [*e[:3], *e[4:]]],
    ids=["reordered", "first-removed", "middle-removed"],
)
def test_reordering_or_removing_events_breaks_the_chain(conversation: list[Event], mutate):
    with pytest.raises(ChainBrokenError):
        verify_chain(mutate(conversation))


def test_an_action_called_but_not_read_back_is_pending_and_never_new():
    f = Factory()
    f.add(EventType.TOOL_CALLED, {"tool": "register_dispute", "idempotency_key": "reg-1"})
    f.add(EventType.TOOL_RESULT, {"tool": "register_dispute", "case_id": "DSP-000001"})
    assert reduce(CONVERSATION, f.events).action_status("reg-1") == "pending"
    f.add(EventType.ACTION_READ_BACK, {"idempotency_key": "reg-1", "matches": False})
    assert reduce(CONVERSATION, f.events).action_status("reg-1") == "pending"
    f.add(EventType.ACTION_READ_BACK, {"idempotency_key": "reg-1", "matches": True})
    assert reduce(CONVERSATION, f.events).action_status("reg-1") == "completed"
    assert reduce(CONVERSATION, f.events).action_status("reg-2") == "new"


def test_events_of_different_conversations_are_never_mixed(conversation: list[Event]):
    with pytest.raises(ValueError, match="same conversation"):
        new_event(conversation[-1], "conv-2", EventType.REPLY, {}, now=lambda: datetime.now(UTC), new_id=lambda: "x")
    with pytest.raises(ValueError, match="another conversation"):
        reduce("conv-2", conversation)
