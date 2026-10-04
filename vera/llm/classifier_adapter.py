"""Interpreter with the learned claim classifier (P42) for the opening claim, behind the interpreter port.

The rules keep the slots, the answers and the safety words; the classifier only reads the claim type of the
opening message, where keyword patterns miss most wordings. Its calibrated probability is the confidence that
POL-14 reads, so below the threshold VERA still asks instead of acting.
"""

from typing import Protocol

from vera.contracts.interpretation import ClaimType, Interpretation
from vera.llm.rules_adapter import RulesInterpreter


class ClaimModel(Protocol):
    def predict(self, text: str) -> tuple[ClaimType, float]: ...


class ClassifierInterpreter:
    name = "classifier"

    def __init__(self, model: ClaimModel, rules: RulesInterpreter | None = None) -> None:
        self._model = model
        self._rules = rules or RulesInterpreter()

    def interpret(self, masked_text: str, context: dict[str, str]) -> Interpretation:
        reading = self._rules.interpret(masked_text, context)
        # A person or a threat found by the rules always wins (POL-01, POL-02).
        if context.get("expecting") != "claim" or reading.claim_type is ClaimType.HUMAN_REQUEST or reading.coercion:
            return reading
        claim, probability = self._model.predict(masked_text)
        return reading.model_copy(update={"claim_type": claim, "confidence": round(probability, 4)})
