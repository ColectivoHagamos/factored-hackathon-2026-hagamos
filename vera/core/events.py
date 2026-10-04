"""Hash-chained events and the reducer that rebuilds a conversation from them.

Every function here is pure: time and identifiers are injected, and storage lives behind the EventLog port.
"""

import hashlib
import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime

from pydantic import JsonValue

from vera.contracts.common import Language
from vera.contracts.events import Event, EventType

PLACEHOLDER_HASH = "0" * 64
IDEMPOTENCY_KEY = "idempotency_key"


class ChainBrokenError(ValueError):
    """The event log was altered, reordered or truncated."""

    def __init__(self, position: int, reason: str) -> None:
        super().__init__(f"event chain broken at position {position}: {reason}")
        self.position = position


def event_hash(event: Event) -> str:
    """SHA-256 of the canonical JSON of the event without its own hash."""
    payload = event.model_dump(mode="json", exclude={"hash"})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def new_event(
    previous: Event | None,
    conversation_id: str,
    event_type: EventType,
    data: dict[str, JsonValue],
    *,
    now: Callable[[], datetime],
    new_id: Callable[[], str],
    llm_provider: str | None = None,
) -> Event:
    """Build the next event of a conversation, chained to the previous one."""
    if previous is not None and previous.conversation_id != conversation_id:
        raise ValueError("an event can only follow an event of the same conversation")
    draft = Event(
        event_id=new_id(),
        conversation_id=conversation_id,
        ts=now(),
        type=event_type,
        data=data,
        llm_provider=llm_provider,
        prev_hash=previous.hash if previous else None,
        hash=PLACEHOLDER_HASH,
    )
    return draft.model_copy(update={"hash": event_hash(draft)})


def verify_chain(events: Sequence[Event]) -> None:
    """Raise ChainBrokenError unless every event is intact and linked to the one before it."""
    previous_hash: str | None = None
    for position, event in enumerate(events):
        if event.prev_hash != previous_hash:
            raise ChainBrokenError(position, "previous hash does not match")
        if event_hash(event) != event.hash:
            raise ChainBrokenError(position, "content does not match its hash")
        previous_hash = event.hash


@dataclass(frozen=True)
class ConversationState:
    """State of a conversation, derived only from its events."""

    conversation_id: str
    last_hash: str | None = None
    customer_turns: int = 0
    language: Language | None = None
    # Idempotency keys of write actions called but not yet read back, and of those confirmed by read-back.
    pending_actions: frozenset[str] = field(default_factory=frozenset)
    completed_actions: frozenset[str] = field(default_factory=frozenset)
    escalated: bool = False
    rules_applied: tuple[str, ...] = ()

    def action_status(self, idempotency_key: str) -> str:
        """Return completed, pending or new; a pending action is read back, never executed again."""
        if idempotency_key in self.completed_actions:
            return "completed"
        return "pending" if idempotency_key in self.pending_actions else "new"


def apply(state: ConversationState, event: Event) -> ConversationState:
    """Fold one event into the state."""
    state = replace(state, last_hash=event.hash)
    key = event.data.get(IDEMPOTENCY_KEY)
    match event.type:
        case EventType.CUSTOMER_MESSAGE:
            return replace(state, customer_turns=state.customer_turns + 1)
        case EventType.INTERPRETATION if isinstance(event.data.get("language"), str):
            return replace(state, language=Language(event.data["language"]))
        case EventType.TOOL_CALLED if isinstance(key, str):
            return replace(state, pending_actions=state.pending_actions | {key})
        case EventType.ACTION_READ_BACK if isinstance(key, str) and event.data.get("matches") is True:
            return replace(
                state,
                pending_actions=state.pending_actions - {key},
                completed_actions=state.completed_actions | {key},
            )
        case EventType.RULE_DECISION if isinstance(event.data.get("rule"), str):
            return replace(state, rules_applied=(*state.rules_applied, event.data["rule"]))
        case EventType.HANDOFF:
            return replace(state, escalated=True)
    return state


def reduce(conversation_id: str, events: Iterable[Event]) -> ConversationState:
    """Rebuild the state of a conversation from its events, in order."""
    state = ConversationState(conversation_id=conversation_id)
    for event in events:
        if event.conversation_id != conversation_id:
            raise ValueError("events of another conversation cannot be reduced into this state")
        state = apply(state, event)
    return state
