"""Port of the interpreter: masked text in, closed schema out. Any adapter (rules or an LLM) fits behind it."""

from typing import Protocol

from vera.contracts.interpretation import Interpretation


class InterpreterPort(Protocol):
    name: str

    def interpret(self, masked_text: str, context: dict[str, str]) -> Interpretation:
        """Fields of one masked customer message; context carries only the language and the pending question."""
        ...
