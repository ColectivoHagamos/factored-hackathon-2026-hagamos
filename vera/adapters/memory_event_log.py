"""In-memory event log for tests and the mock demo."""

from collections import defaultdict

from vera.contracts.events import Event
from vera.ports.event_log import StaleAppendError


class MemoryEventLog:
    def __init__(self) -> None:
        self._events: defaultdict[str, list[Event]] = defaultdict(list)

    def append(self, event: Event) -> None:
        stored = self._events[event.conversation_id]
        last_hash = stored[-1].hash if stored else None
        if event.prev_hash != last_hash:
            raise StaleAppendError(f"event {event.event_id} does not follow the last stored event")
        stored.append(event)

    def read(self, conversation_id: str) -> tuple[Event, ...]:
        return tuple(self._events.get(conversation_id, ()))
