"""Port of the append-only event log."""

from typing import Protocol

from vera.contracts.events import Event


class StaleAppendError(RuntimeError):
    """The event does not follow the last stored event: another writer appended first."""


class EventLog(Protocol):
    def append(self, event: Event) -> None:
        """Store the event if it follows the last one of its conversation; raise StaleAppendError otherwise."""
        ...

    def read(self, conversation_id: str) -> tuple[Event, ...]:
        """Return the events of a conversation in the order they were appended."""
        ...
