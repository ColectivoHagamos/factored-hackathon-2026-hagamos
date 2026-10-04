"""Contract tests of the EventLog port: every adapter must pass the same tests."""

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from vera.adapters.memory_event_log import MemoryEventLog
from vera.adapters.sqlite_event_log import SqliteEventLog
from vera.contracts.events import Event, EventType
from vera.core.events import new_event, reduce, verify_chain
from vera.ports.event_log import EventLog, StaleAppendError


def chain(conversation_id: str, *types: EventType, data: dict | None = None) -> list[Event]:
    events: list[Event] = []
    for n, event_type in enumerate(types, 1):
        events.append(
            new_event(
                events[-1] if events else None,
                conversation_id,
                event_type,
                data or {},
                now=lambda: datetime(2026, 6, 18, 15, 0, tzinfo=UTC),
                new_id=lambda n=n: f"{conversation_id}-{n}",
            )
        )
    return events


@pytest.fixture(params=["memory", "sqlite"])
def log(request, tmp_path: Path) -> Iterator[EventLog]:
    if request.param == "memory":
        yield MemoryEventLog()
        return
    adapter = SqliteEventLog(tmp_path / "state.sqlite")
    yield adapter
    adapter.close()


def test_events_are_read_back_in_append_order(log: EventLog):
    events = chain("conv-a", EventType.CUSTOMER_MESSAGE, EventType.INTERPRETATION, EventType.REPLY)
    for event in events:
        log.append(event)
    assert log.read("conv-a") == tuple(events)
    verify_chain(log.read("conv-a"))
    assert log.read("conv-unknown") == ()


def test_conversations_are_isolated(log: EventLog):
    for event in chain("conv-a", EventType.CUSTOMER_MESSAGE) + chain("conv-b", EventType.CUSTOMER_MESSAGE):
        log.append(event)
    assert [e.conversation_id for e in log.read("conv-b")] == ["conv-b"]


@pytest.mark.parametrize("position", [0, 1])
def test_an_event_that_does_not_follow_the_last_one_is_rejected(log: EventLog, position: int):
    events = chain("conv-a", EventType.CUSTOMER_MESSAGE, EventType.REPLY)
    log.append(events[0])
    with pytest.raises(StaleAppendError):
        log.append(events[position] if position == 0 else chain("conv-a", EventType.REPLY)[0])
    assert log.read("conv-a") == (events[0],)


def test_sqlite_log_forbids_updates_and_deletes_and_survives_a_restart(tmp_path: Path):
    path = tmp_path / "state.sqlite"
    log = SqliteEventLog(path)
    data = {"tool": "register_dispute", "idempotency_key": "reg-1"}
    for event in chain("conv-a", EventType.TOOL_CALLED, EventType.TOOL_RESULT, data=data):
        log.append(event)
    log.close()
    raw = sqlite3.connect(path)
    for statement in ("UPDATE events SET body = '{}'", "DELETE FROM events"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            raw.execute(statement)
    raw.close()
    # After a crash between the call and the read-back, the action is pending: it is read back, not executed again.
    restarted = SqliteEventLog(path)
    assert reduce("conv-a", restarted.read("conv-a")).action_status("reg-1") == "pending"
    restarted.close()
