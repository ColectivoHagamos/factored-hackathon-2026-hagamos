"""Writable state of the demo in SQLite: cases, card blocks, handoffs and transfers, each idempotent by key.

The API serves requests from several threads and a SQLite connection cannot be used by two at once, so every
statement, read or write, runs under one reentrant lock and fetches its rows before releasing it.
"""

import sqlite3
import threading
from pathlib import Path

from vera.contracts.cases import Case
from vera.contracts.handoff import Handoff, Queue, Transfer
from vera.ports.bank import FraudAlertRecord

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
CREATE TABLE IF NOT EXISTS transfers (
    transfer_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL UNIQUE,
    queue TEXT NOT NULL,
    body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    customer_ref TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fraud_alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT,
    customer_ref TEXT NOT NULL,
    signals TEXT NOT NULL,
    charge_refs TEXT NOT NULL,
    card_blocked INTEGER NOT NULL
);
"""


class SqliteState:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._connection = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
        self._lock = threading.RLock()
        self._connection.executescript(SCHEMA)

    def _one(self, sql: str, parameters: tuple = ()) -> tuple | None:
        with self._lock:
            return self._connection.execute(sql, parameters).fetchone()

    def _all(self, sql: str, parameters: tuple = ()) -> list[tuple]:
        with self._lock:
            return self._connection.execute(sql, parameters).fetchall()

    def register(self, case: Case, customer_ref: str, charge_refs: tuple[str, ...], idempotency_key: str) -> Case:
        """Store the case once per key; a repeated key returns the case stored the first time.

        The case id is assigned here, under the lock, so two registrations at the same time never share one.
        """
        with self._lock:
            found = self._one("SELECT body FROM cases WHERE idempotency_key = ?", (idempotency_key,))
            if found:
                return Case.model_validate_json(found[0])
            case = case.model_copy(update={"case_id": self.next_case_id()})
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
        row = self._one("SELECT body FROM cases WHERE case_id = ? AND customer_ref = ?", (case_id, customer_ref))
        return Case.model_validate_json(row[0]) if row else None

    def case_with_charge(self, charge_ref: str) -> str | None:
        row = self._one("SELECT case_id FROM case_charges WHERE charge_ref = ?", (charge_ref,))
        return row[0] if row else None

    def charges_of_case(self, case_id: str) -> tuple[str, ...]:
        rows = self._all("SELECT charge_ref FROM case_charges WHERE case_id = ?", (case_id,))
        return tuple(sorted(row[0] for row in rows))

    def cases_of(self, customer_ref: str) -> tuple[str, ...]:
        rows = self._all("SELECT case_id FROM cases WHERE customer_ref = ? ORDER BY case_id", (customer_ref,))
        return tuple(row[0] for row in rows)

    def next_case_id(self) -> str:
        return f"DSP-{self._one('SELECT count(*) FROM cases')[0] + 1:06d}"

    def record_block(self, card_ref: str, idempotency_key: str) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT OR IGNORE INTO card_blocks (card_ref, idempotency_key) VALUES (?, ?)",
                (card_ref, idempotency_key),
            )

    def blocked_cards(self) -> frozenset[str]:
        return frozenset(row[0] for row in self._all("SELECT card_ref FROM card_blocks"))

    def hand_off(self, handoff: Handoff, queue: Queue) -> str:
        with self._lock:
            cursor = self._connection.execute(
                "INSERT INTO handoffs (case_id, queue, body) VALUES (?, ?, ?)",
                (handoff.case_id, queue.value, handoff.model_dump_json()),
            )
            return f"HND-{cursor.lastrowid:06d}"

    def handoff_of(self, case_id: str) -> Handoff | None:
        row = self._one("SELECT body FROM handoffs WHERE case_id = ? ORDER BY handoff_id DESC LIMIT 1", (case_id,))
        return Handoff.model_validate_json(row[0]) if row else None

    def transfer(self, note: Transfer, conversation_id: str) -> Transfer:
        with self._lock:
            row = self._one("SELECT body FROM transfers WHERE conversation_id = ?", (conversation_id,))
            if row:
                return Transfer.model_validate_json(row[0])
            count = self._one("SELECT count(*) FROM transfers")[0]
            stored = note.model_copy(update={"transfer_id": f"TRF-{count + 1:06d}"})
            self._connection.execute(
                "INSERT INTO transfers (transfer_id, conversation_id, queue, body) VALUES (?, ?, ?, ?)",
                (stored.transfer_id, conversation_id, stored.suggested_queue.value, stored.model_dump_json()),
            )
            return stored

    def transfer_of(self, transfer_id: str) -> Transfer | None:
        row = self._one("SELECT body FROM transfers WHERE transfer_id = ?", (transfer_id,))
        return Transfer.model_validate_json(row[0]) if row else None

    def queue(self, limit: int = 50) -> tuple[Handoff | Transfer, ...]:
        """What is waiting for an analyst, newest first: the latest handoff of each case and every transfer."""
        handoffs = self._all(
            "SELECT body FROM handoffs WHERE handoff_id IN (SELECT max(handoff_id) FROM handoffs GROUP BY case_id)"
        )
        transfers = self._all("SELECT body FROM transfers")
        items = [Handoff.model_validate_json(row[0]) for row in handoffs]
        items += [Transfer.model_validate_json(row[0]) for row in transfers]
        return tuple(sorted(items, key=lambda item: item.created_at, reverse=True)[:limit])

    def fraud_alert(self, alert: FraudAlertRecord) -> str:
        with self._lock:
            cursor = self._connection.execute(
                "INSERT INTO fraud_alerts (case_id, customer_ref, signals, charge_refs, card_blocked) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    alert.case_id,
                    alert.customer_ref,
                    ",".join(alert.signals),
                    ",".join(alert.charge_refs),
                    int(alert.card_blocked),
                ),
            )
            return f"ALR-{cursor.lastrowid:06d}"

    def fraud_alerts_of(self, customer_ref: str) -> tuple[FraudAlertRecord, ...]:
        rows = self._all(
            "SELECT case_id, signals, charge_refs, card_blocked FROM fraud_alerts WHERE customer_ref = ? "
            "ORDER BY alert_id",
            (customer_ref,),
        )
        return tuple(
            FraudAlertRecord(customer_ref, case_id, tuple(signals.split(",")), tuple(refs.split(",")), bool(blocked))
            for case_id, signals, refs, blocked in rows
        )

    def open_conversation(self, conversation_id: str, customer_ref: str) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT INTO conversations (conversation_id, customer_ref) VALUES (?, ?)",
                (conversation_id, customer_ref),
            )

    def conversation_owner(self, conversation_id: str) -> str | None:
        row = self._one("SELECT customer_ref FROM conversations WHERE conversation_id = ?", (conversation_id,))
        return row[0] if row else None

    def close(self) -> None:
        self._connection.close()
