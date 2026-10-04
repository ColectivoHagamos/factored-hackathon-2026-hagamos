"""SQLite event log. Append-only is enforced by the database itself, not only by this code."""

import sqlite3
from pathlib import Path

from vera.contracts.events import Event
from vera.ports.event_log import StaleAppendError

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    conversation_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    event_id TEXT NOT NULL UNIQUE,
    hash TEXT NOT NULL UNIQUE,
    prev_hash TEXT,
    body TEXT NOT NULL,
    PRIMARY KEY (conversation_id, seq)
);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
"""


class SqliteEventLog:
    def __init__(self, path: str | Path) -> None:
        self._connection = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
        self._connection.executescript(SCHEMA)

    def append(self, event: Event) -> None:
        # BEGIN IMMEDIATE takes the write lock before reading the last hash, so two writers cannot both pass.
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            last = self._connection.execute(
                "SELECT seq, hash FROM events WHERE conversation_id = ? ORDER BY seq DESC LIMIT 1",
                (event.conversation_id,),
            ).fetchone()
            last_seq, last_hash = last if last else (0, None)
            if event.prev_hash != last_hash:
                raise StaleAppendError(f"event {event.event_id} does not follow the last stored event")
            self._connection.execute(
                "INSERT INTO events (conversation_id, seq, event_id, hash, prev_hash, body) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event.conversation_id,
                    last_seq + 1,
                    event.event_id,
                    event.hash,
                    event.prev_hash,
                    event.model_dump_json(),
                ),
            )
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")

    def read(self, conversation_id: str) -> tuple[Event, ...]:
        rows = self._connection.execute(
            "SELECT body FROM events WHERE conversation_id = ? ORDER BY seq", (conversation_id,)
        ).fetchall()
        return tuple(Event.model_validate_json(body) for (body,) in rows)

    def close(self) -> None:
        self._connection.close()
