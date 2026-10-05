"""Wiring: the only place that chooses adapters, from the settings."""

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from api.observability import log_event
from api.security import SessionSigner
from api.settings import Settings
from vera.adapters.demo_bank import DemoBank
from vera.adapters.memory_event_log import MemoryEventLog
from vera.adapters.mock_bank import MockBank
from vera.adapters.sqlite_event_log import SqliteEventLog
from vera.adapters.sqlite_state import SqliteState
from vera.core.flow import Conversation
from vera.llm.anthropic_adapter import AnthropicInterpreter
from vera.llm.classifier_adapter import ClassifierInterpreter
from vera.llm.rules_adapter import RulesInterpreter
from vera.output.render import Renderer
from vera.policy.engine import PolicyEngine
from vera.policy.legal_clock import LegalClock
from vera.policy.model import load_policy
from vera.ports.bank import CardsPort, CustomersPort, TransactionsPort
from vera.ports.interpreter import InterpreterPort
from vera.tools.gate import ActionGate
from vera.tools.service import ToolService
from vera.tools.toolbox import Toolbox


@dataclass
class Container:
    settings: Settings
    state: SqliteState
    customers: CustomersPort
    # The cards and movements of the session customer, as the bank's app shows them.
    cards: CardsPort
    transactions: TransactionsPort
    tools: ToolService
    conversation: Conversation
    signer: SessionSigner
    now: Callable[[], datetime]
    # The interpreter actually in use; degraded when the configured one could not start.
    interpreter: str = "rules"
    degraded: bool = False
    # Calls, tokens and spending of the language model, when one is in use (P41).
    llm_usage: Callable[[], dict] | None = None


def wall_clock() -> datetime:
    """Real time with its zone: sessions and confirmations expire in real time, whatever day the demo lives on."""
    return datetime.now(UTC)


def simulated_clock() -> Callable[[], datetime]:
    """The demo lives on the last day of the dataset (policy system_clock), with the real time of day."""
    clock_day = load_policy().parameters.system_clock

    def now() -> datetime:
        # Local time without zone, like the timestamps of the transactions; events add the zone when stored.
        return datetime.now().replace(year=clock_day.year, month=clock_day.month, day=clock_day.day)

    return now


def interpreter_for(settings: Settings) -> tuple[InterpreterPort, bool]:
    """The configured interpreter, or the rules when it cannot start: the service answers either way (P54)."""
    builders = {"classifier": _classifier, "anthropic": lambda: _anthropic(settings)}
    if settings.llm not in builders:
        return RulesInterpreter(), False
    try:
        return builders[settings.llm](), False
    except Exception as error:  # any failure to start leaves the rules in charge, and health says degraded
        log_event("interpreter_fallback", configured=settings.llm, using="rules", error=type(error).__name__)
        return RulesInterpreter(), True


def _classifier() -> InterpreterPort:
    # Imported here so the rules interpreter never loads scikit-learn; trained once per process, no model file.
    from ml.claims import default_classifier

    return ClassifierInterpreter(default_classifier())


def _anthropic(settings: Settings) -> AnthropicInterpreter:
    """Claude reads the messages; the classifier, or the rules, answers when it cannot and stays as the floor."""
    if not settings.llm_api_key:
        raise ValueError("LLM_API_KEY is empty")
    import anthropic

    try:
        fallback = _classifier()
    except Exception:  # without the classifier the floor is the rules; the start-up goes on
        fallback = RulesInterpreter()
    workspace = {"anthropic-workspace-id": settings.llm_workspace_id} if settings.llm_workspace_id else None
    client = anthropic.Anthropic(
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout_seconds,
        max_retries=2,
        default_headers=workspace,
    )
    cap = Decimal(str(settings.llm_max_spend_usd))
    interpreter = AnthropicInterpreter(client.messages, settings.llm_model, cap, fallback)
    log_event("interpreter", using="anthropic", model=interpreter.model, prompt=interpreter.prompt_version)
    return interpreter


def build(
    settings: Settings,
    now: Callable[[], datetime] | None = None,
    bank_factory: Callable[[SqliteState], DemoBank | MockBank] | None = None,
) -> Container:
    """The application; bank_factory replaces the configured adapter, as the evaluation does to make a tool fail."""
    # Tests inject one clock for everything. Otherwise the conversation lives on the demo's day, while what expires
    # for security (sessions and confirmations) follows real time: the demo's day repeats, real time never does.
    expiry = now or wall_clock
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
    gate = ActionGate(toolbox, secret=settings.session_secret.encode(), now=expiry)
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
    signer = SessionSigner(settings.session_secret, expiry)
    usage = interpreter.spending.snapshot if isinstance(interpreter, AnthropicInterpreter) else None
    return Container(
        settings=settings,
        state=state,
        customers=bank,
        cards=bank,
        transactions=bank,
        tools=tools,
        conversation=conversation,
        signer=signer,
        now=now,
        interpreter=interpreter.name,
        degraded=degraded,
        llm_usage=usage,
    )
