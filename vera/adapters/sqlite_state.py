"""Writable state of the demo in SQLite: cases, card blocks and handoffs, each idempotent by key."""

import sqlite3
import threading
from pathlib import Path

from vera.contracts.cases import Case
from vera.contracts.handoff import Handoff, Queue

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    customer_ref TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS case_charges (
    charge_ref TEXT PRIMARY KEY,
    case_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS card_blocks (
    card_ref TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS handoffs (
    handoff_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    queue TEXT NOT NULL,
    body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fraud_alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT,
    customer_ref TEXT NOT NULL,
    signals TEXT NOT NULL
);
"""


class SqliteState:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._connection = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
        self._lock = threading.Lock()
        self._connection.executescript(SCHEMA)

    def register(self, case: Case, customer_ref: str, charge_refs: tuple[str, ...], idempotency_key: str) -> Case:
        """Store the case once per key; a repeated key returns the case stored the first time."""
        with self._lock:
            found = self._connection.execute(
                "SELECT body FROM cases WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
            if found:
                return Case.model_validate_json(found[0])
            self._connection.execute("BEGIN")
            try:
                self._connection.execute(
                    "INSERT INTO cases (case_id, customer_ref, idempotency_key, body) VALUES (?, ?, ?, ?)",
                    (case.case_id, customer_ref, idempotency_key, case.model_dump_json()),
                )
                self._connection.executemany(
                    "INSERT INTO case_charges (charge_ref, case_id) VALUES (?, ?)",
                    [(ref, case.case_id) for ref in charge_refs],
                )
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
            self._connection.execute("COMMIT")
            return case

    def read(self, case_id: str, customer_ref: str) -> Case | None:
        """The case, only for its own customer: another customer's case reads as not found."""
        row = self._connection.execute(
            "SELECT body FROM cases WHERE case_id = ? AND customer_ref = ?", (case_id, customer_ref)
        ).fetchone()
        return Case.model_validate_json(row[0]) if row else None

    def case_with_charge(self, charge_ref: str) -> str | None:
        row = self._connection.execute(
            "SELECT case_id FROM case_charges WHERE charge_ref = ?", (charge_ref,)
        ).fetchone()
        return row[0] if row else None

    def cases_of(self, customer_ref: str) -> tuple[str, ...]:
        rows = self._connection.execute(
            "SELECT case_id FROM cases WHERE customer_ref = ? ORDER BY case_id", (customer_ref,)
        )
        return tuple(row[0] for row in rows)

    def next_case_id(self) -> str:
        count = self._connection.execute("SELECT count(*) FROM cases").fetchone()[0]
        return f"DSP-{count + 1:06d}"

    def record_block(self, card_ref: str, idempotency_key: str) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT OR IGNORE INTO card_blocks (card_ref, idempotency_key) VALUES (?, ?)",
                (card_ref, idempotency_key),
            )

    def blocked_cards(self) -> frozenset[str]:
        return frozenset(row[0] for row in self._connection.execute("SELECT card_ref FROM card_blocks"))

    def hand_off(self, handoff: Handoff, queue: Queue) -> str:
        with self._lock:
            cursor = self._connection.execute(
                "INSERT INTO handoffs (case_id, queue, body) VALUES (?, ?, ?)",
                (handoff.case_id, queue.value, handoff.model_dump_json()),
            )
            return f"HND-{cursor.lastrowid:06d}"

    def handoff_of(self, case_id: str) -> Handoff | None:
        row = self._connection.execute(
            "SELECT body FROM handoffs WHERE case_id = ? ORDER BY handoff_id DESC LIMIT 1", (case_id,)
        ).fetchone()
        return Handoff.model_validate_json(row[0]) if row else None

    def fraud_alert(self, case_id: str | None, customer_ref: str, signals: tuple[str, ...]) -> str:
        with self._lock:
            cursor = self._connection.execute(
                "INSERT INTO fraud_alerts (case_id, customer_ref, signals) VALUES (?, ?, ?)",
                (case_id, customer_ref, ",".join(signals)),
            )
            return f"ALR-{cursor.lastrowid:06d}"

    def close(self) -> None:
        self._connection.close()
