"""In-memory event log for tests and the mock demo."""

import threading
from collections import defaultdict

from vera.contracts.events import Event
from vera.ports.event_log import StaleAppendError


class MemoryEventLog:
    def __init__(self) -> None:
        self._events: defaultdict[str, list[Event]] = defaultdict(list)
        # The check of the last hash and the append are one step, also when the API serves several threads.
        self._lock = threading.Lock()

    def append(self, event: Event) -> None:
        with self._lock:
            stored = self._events[event.conversation_id]
            last_hash = stored[-1].hash if stored else None
            if event.prev_hash != last_hash:
                raise StaleAppendError(f"event {event.event_id} does not follow the last stored event")
            stored.append(event)

    def read(self, conversation_id: str) -> tuple[Event, ...]:
        with self._lock:
            return tuple(self._events.get(conversation_id, ()))
