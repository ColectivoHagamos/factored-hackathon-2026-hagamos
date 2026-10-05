"""Each adapter implements the ports it is wired to, method by method, with the same parameters.

The ports are structural protocols, so nothing at run time stops an adapter from drifting away from one; this test
does, for every pair the composition root (api/dependencies.py) or a test double relies on.
"""

import inspect

import pytest

from vera.adapters.demo_bank import DemoBank
from vera.adapters.memory_event_log import MemoryEventLog
from vera.adapters.mock_bank import MockBank
from vera.adapters.sqlite_event_log import SqliteEventLog
from vera.adapters.sqlite_state import SqliteState
from vera.llm.anthropic_adapter import AnthropicInterpreter
from vera.llm.classifier_adapter import ClassifierInterpreter
from vera.llm.rules_adapter import RulesInterpreter
from vera.ports.bank import AnalystQueuePort, CardsPort, CasesPort, CustomersPort, RoutingPort, TransactionsPort
from vera.ports.conversations import ConversationOwnersPort
from vera.ports.event_log import EventLog
from vera.ports.interpreter import InterpreterPort
from vera.ports.tools import ToolsPort
from vera.tools.service import ToolService

WIRING = [
    (DemoBank, CustomersPort),
    (DemoBank, TransactionsPort),
    (DemoBank, CardsPort),
    (MockBank, CustomersPort),
    (MockBank, TransactionsPort),
    (MockBank, CardsPort),
    (SqliteState, CasesPort),
    (SqliteState, RoutingPort),
    (SqliteState, AnalystQueuePort),
    (SqliteState, ConversationOwnersPort),
    (SqliteEventLog, EventLog),
    (MemoryEventLog, EventLog),
    (AnthropicInterpreter, InterpreterPort),
    (ClassifierInterpreter, InterpreterPort),
    (RulesInterpreter, InterpreterPort),
    (ToolService, ToolsPort),
]


def port_methods(port: type) -> dict[str, inspect.Signature]:
    """The methods a protocol declares, by name, without the members every class has."""
    return {
        name: inspect.signature(member)
        for name, member in vars(port).items()
        if callable(member) and not name.startswith("_")
    }


def parameter_names(signature: inspect.Signature) -> list[str]:
    return [name for name in signature.parameters if name != "self"]


def mismatches(adapter: type, port: type) -> list[str]:
    """What the adapter lacks of the port, or takes differently."""
    found = []
    for name, declared in port_methods(port).items():
        implemented = getattr(adapter, name, None)
        if not callable(implemented):
            found.append(f"{adapter.__name__} lacks {port.__name__}.{name}")
        elif parameter_names(inspect.signature(implemented)) != parameter_names(declared):
            found.append(f"{adapter.__name__}.{name} does not take the parameters of {port.__name__}.{name}")
    return found


@pytest.mark.parametrize(("adapter", "port"), WIRING, ids=lambda item: item.__name__)
def test_adapter_implements_its_port(adapter: type, port: type):
    assert mismatches(adapter, port) == []


def test_the_port_check_finds_a_drifted_adapter():
    # Positive control: an adapter that renamed a parameter and lost a method fails the same check.
    class Drifted:
        def open_conversation(self, conversation, customer) -> None: ...

    assert mismatches(Drifted, ConversationOwnersPort) == [
        "Drifted.open_conversation does not take the parameters of ConversationOwnersPort.open_conversation",
        "Drifted lacks ConversationOwnersPort.conversation_owner",
    ]
