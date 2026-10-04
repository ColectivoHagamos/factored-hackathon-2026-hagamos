"""Concurrency (P54): the API serves requests from several threads, and the state and the event logs stay whole.

The load test found the failure these tests pin: one SQLite connection used by two threads at once, and two
registrations at the same time computing the same case id.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from vera.adapters.memory_event_log import MemoryEventLog
from vera.adapters.mock_bank import CLOCK, CUSTOMERS, MockBank
from vera.adapters.sqlite_event_log import SqliteEventLog
from vera.adapters.sqlite_state import SqliteState
from vera.contracts.events import EventType
from vera.contracts.tools import RegisterDisputeInput, SearchChargesInput, ToolError
from vera.core.events import new_event, verify_chain
from vera.policy.model import load_policy
from vera.ports.tools import Offers, Session
from vera.tools.toolbox import Toolbox

TOKEN = "tok_" + "a1b2c3d4" * 3
WINDOW = SearchChargesInput(date_from=date(2025, 1, 1), date_to=date(2026, 6, 18))


def test_registrations_at_the_same_time_get_distinct_case_ids(tmp_path: Path):
    state = SqliteState(tmp_path / "state.sqlite")
    bank = MockBank(state)
    tools = Toolbox(bank, bank, state, state, load_policy().parameters.usd_rates, now=lambda: CLOCK)
    targets = []
    for customer in CUSTOMERS:
        result = tools.search_charges(Session(customer.customer_ref, "probe"), Offers(), WINDOW)
        if not isinstance(result, ToolError):
            output, offers = result
            targets += [(customer.customer_ref, candidate.n, offers) for candidate in output.candidates]

    def register(index: int):
        customer, n, offers = targets[index]
        args = RegisterDisputeInput(charges_n=[n], reason="fraud", declared_channel="online", confirmation_token=TOKEN)
        return tools.register_dispute(
            Session(customer, f"conv-{index}"), offers, args, claim_type="unrecognized_charge"
        )

    with ThreadPoolExecutor(max_workers=12) as pool:
        outputs = list(pool.map(register, range(len(targets))))
    case_ids = [output.case_id for output in outputs if not isinstance(output, ToolError)]
    assert len(case_ids) >= 5 and len(set(case_ids)) == len(case_ids)


def test_conversations_opened_and_read_from_many_threads_never_collide(tmp_path: Path):
    state = SqliteState(tmp_path / "state.sqlite")

    def open_and_read(index: int) -> str | None:
        state.open_conversation(f"conv-{index}", f"customer-{index % 7}")
        return state.conversation_owner(f"conv-{index}")

    with ThreadPoolExecutor(max_workers=16) as pool:
        owners = list(pool.map(open_and_read, range(200)))
    assert owners == [f"customer-{index % 7}" for index in range(200)]


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
def test_chains_stay_whole_when_many_conversations_append_at_once(kind: str, tmp_path: Path):
    log = MemoryEventLog() if kind == "memory" else SqliteEventLog(tmp_path / "events.sqlite")

    def converse(index: int) -> None:
        previous = None
        for step in range(12):
            event = new_event(
                previous,
                f"conv-{index}",
                EventType.CUSTOMER_MESSAGE if step % 2 == 0 else EventType.REPLY,
                {"step": step},
                now=lambda: datetime(2026, 6, 18, 15, 0, tzinfo=UTC),
                new_id=lambda step=step: f"conv-{index}-{step}",
            )
            log.append(event)
            previous = event

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(converse, range(40)))
    for index in range(40):
        events = log.read(f"conv-{index}")
        assert len(events) == 12
        verify_chain(events)
