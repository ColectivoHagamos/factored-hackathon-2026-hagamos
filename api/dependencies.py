"""Wiring: the only place that chooses adapters, from the settings."""

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from api.observability import log_event
from api.security import SessionSigner
from api.settings import Settings
from vera.adapters.demo_bank import DemoBank
from vera.adapters.memory_event_log import MemoryEventLog
from vera.adapters.mock_bank import MockBank
from vera.adapters.sqlite_event_log import SqliteEventLog
from vera.adapters.sqlite_state import SqliteState
from vera.core.flow import Conversation
from vera.llm.classifier_adapter import ClassifierInterpreter
from vera.llm.rules_adapter import RulesInterpreter
from vera.output.render import Renderer
from vera.policy.engine import PolicyEngine
from vera.policy.legal_clock import LegalClock
from vera.policy.model import load_policy
from vera.ports.bank import CustomersPort
from vera.ports.interpreter import InterpreterPort
from vera.tools.gate import ActionGate
from vera.tools.service import ToolService
from vera.tools.toolbox import Toolbox


@dataclass
class Container:
    settings: Settings
    state: SqliteState
    customers: CustomersPort
    tools: ToolService
    conversation: Conversation
    signer: SessionSigner
    now: Callable[[], datetime]
    # The interpreter actually in use; degraded when the configured one could not start.
    interpreter: str = "rules"
    degraded: bool = False


def simulated_clock() -> Callable[[], datetime]:
    """The demo lives on the last day of the dataset (policy system_clock), with the real time of day."""
    clock_day = load_policy().parameters.system_clock

    def now() -> datetime:
        # Local time without zone, like the timestamps of the transactions; events add the zone when stored.
        return datetime.now().replace(year=clock_day.year, month=clock_day.month, day=clock_day.day)

    return now


def interpreter_for(settings: Settings) -> tuple[InterpreterPort, bool]:
    """The configured interpreter, or the rules when it cannot start: the service answers either way (P54)."""
    if settings.llm == "classifier":
        try:
            # Imported here so the rules interpreter never loads scikit-learn; trained once per process, no model file.
            from ml.claims import default_classifier

            return ClassifierInterpreter(default_classifier()), False
        except Exception as error:  # any failure to start the model leaves the rules in charge
            log_event("interpreter_fallback", configured="classifier", using="rules", error=type(error).__name__)
            return RulesInterpreter(), True
    return RulesInterpreter(), False


def build(
    settings: Settings,
    now: Callable[[], datetime] | None = None,
    bank_factory: Callable[[SqliteState], DemoBank | MockBank] | None = None,
) -> Container:
    """The application; bank_factory replaces the configured adapter, as the evaluation does to make a tool fail."""
    now = now or simulated_clock()
    policy = load_policy()
    state = SqliteState(settings.state_db)
    if bank_factory:
        bank = bank_factory(state)
    elif settings.adapter == "dataset":
        bank = DemoBank(settings.demo_db, state)
    else:
        bank = MockBank(state)
    toolbox = Toolbox(bank, bank, state, state, policy.parameters.usd_rates, now=now)
    gate = ActionGate(toolbox, secret=settings.session_secret.encode(), now=now)
    tools = ToolService(toolbox, gate, bank, bank, now=now)
    log = SqliteEventLog(settings.state_db) if settings.state_db != ":memory:" else MemoryEventLog()
    interpreter, degraded = interpreter_for(settings)
    conversation = Conversation(
        interpreter=interpreter,
        tools=tools,
        log=log,
        engine=PolicyEngine(policy),
        legal=LegalClock.from_files(),
        renderer=Renderer(),
        now=now,
        new_id=lambda: secrets.token_hex(8),
    )
    signer = SessionSigner(settings.session_secret, now)
    return Container(settings, state, bank, tools, conversation, signer, now, interpreter.name, degraded)
