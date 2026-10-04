"""A fake of the Anthropic Messages API for the tests of the language model interpreter (P41): no network, no key."""

from types import SimpleNamespace

from vera.llm.anthropic_adapter import TOOL

READ = {
    "claim_type": "unrecognized_charge",
    "merchant_text": "Libreria Andina",
    "amount": 185000,
    "currency": "COP",
    "answer": "not_said",
    "language": "es",
    "confidence": 0.92,
}
# A model that reads every message wrong, to show what it can never hide.
WRONG = {"claim_type": "out_of_scope", "answer": "not_said", "language": "es", "confidence": 0.99}


def reply(fields: dict, input_tokens: int = 1500, output_tokens: int = 200) -> SimpleNamespace:
    """A response of the Messages API carrying the one forced tool call."""
    block = SimpleNamespace(type="tool_use", name=TOOL, input=fields)
    usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
    return SimpleNamespace(content=[block], usage=usage)


class FakeMessages:
    """Stands for client.messages: it records each request and answers with a response or an error."""

    def __init__(self, *responses) -> None:
        self.responses = list(responses)
        self.requests: list[dict] = []

    def create(self, **request):
        self.requests.append(request)
        response = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(response, Exception):
            raise response
        return response
