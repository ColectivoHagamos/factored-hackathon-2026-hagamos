"""Tests of the tool service (POL-13): adapter failures become typed tool errors, and reads are tried twice."""

from datetime import date

from vera.adapters.mock_bank import CLOCK, MockBank
from vera.adapters.sqlite_state import SqliteState
from vera.contracts.tools import SearchChargesInput, ToolError
from vera.policy.model import load_policy
from vera.ports.tools import Offers, Session
from vera.tools.gate import ActionGate
from vera.tools.service import ToolService
from vera.tools.toolbox import Toolbox

WINDOW = SearchChargesInput(date_from=date(2026, 6, 1), date_to=date(2026, 6, 18))
CO_02 = Session("CUS-MOCK00000000002", "conv-1")


class Flaky(MockBank):
    """Fails the first given number of reads of charges, then answers."""

    failures = 1

    def __init__(self, state: SqliteState) -> None:
        super().__init__(state)
        self.calls = 0

    def charges(self, customer_ref, since, until):
        self.calls += 1
        if self.calls <= self.failures:
            raise ConnectionError("the transactions store is restarting")
        return super().charges(customer_ref, since, until)


def service(bank: MockBank, state: SqliteState) -> ToolService:
    now = lambda: CLOCK  # noqa: E731
    toolbox = Toolbox(bank, bank, state, state, load_policy().parameters.usd_rates, now=now)
    return ToolService(toolbox, ActionGate(toolbox, b"secret", now=now), bank, bank, now=now)


def test_a_read_that_fails_once_is_tried_again_and_answers():
    state = SqliteState()
    bank = Flaky(state)
    output, _ = service(bank, state).search_charges(CO_02, Offers(), WINDOW)
    assert len(output.candidates) == 3 and bank.calls == 2


def test_a_read_that_keeps_failing_is_a_failure_error_not_a_crash():
    state = SqliteState()
    bank = Flaky(state)
    bank.failures = 5
    assert service(bank, state).search_charges(CO_02, Offers(), WINDOW) == ToolError(code="failure")
    assert bank.calls == 2
