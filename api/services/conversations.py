"""A customer's conversation over HTTP: who owns it, how many messages a minute, and what reaches the core."""

import secrets
import time

from api.failures import ApiFailure
from api.limits import RateLimiter
from api.observability import Metrics, log_event, turn_summary
from api.schemas import ApiErrorCode, StartConversationResponse
from api.services.demo import DemoDirectory
from vera.contracts.common import Language
from vera.contracts.conversation import MessageRequest, MessageResponse
from vera.core.flow import Conversation
from vera.gateway.injection import signals as injection_signals
from vera.gateway.masking import mask
from vera.ports.conversations import ConversationOwnersPort
from vera.ports.tools import Session


class ConversationService:
    def __init__(
        self,
        conversation: Conversation,
        owners: ConversationOwnersPort,
        demo: DemoDirectory,
        metrics: Metrics,
        messages: RateLimiter,
    ) -> None:
        self._conversation = conversation
        self._owners = owners
        self._demo = demo
        self._metrics = metrics
        self._messages = messages

    def start(self, customer_ref: str, preferred_language: Language | None) -> StartConversationResponse:
        conversation_id = secrets.token_hex(8)
        self._owners.open_conversation(conversation_id, customer_ref)
        persona = self._demo.persona(customer_ref)
        opening = self._conversation.start(
            Session(customer_ref, conversation_id),
            preferred_language,
            first_name=persona.first_name if persona else None,
        )
        self._metrics.conversation()
        return StartConversationResponse(
            conversation_id=conversation_id, greeting=opening.reply, options=opening.options
        )

    def reply(self, customer_ref: str, conversation_id: str, body: MessageRequest, request_id: str) -> MessageResponse:
        # A conversation of another customer answers exactly like one that does not exist.
        if self._owners.conversation_owner(conversation_id) != customer_ref:
            raise ApiFailure(ApiErrorCode.NOT_FOUND)
        self._messages.check(customer_ref)
        # Injection signals are read on the original text; only the masked text goes further.
        signals = injection_signals(body.text) if body.text else ()
        masked = body.model_copy(update={"text": mask(body.text)}) if body.text else body
        started = time.perf_counter()
        reply = self._conversation.reply(Session(customer_ref, conversation_id), masked, signals)
        ms = round((time.perf_counter() - started) * 1000, 1)
        # The conversation id is the trace id: these lines and the hash-chained event log tell the same turn.
        summary = turn_summary(self._conversation.history(conversation_id))
        self._metrics.turn(summary, ms)
        log_event("turn", trace_id=f"trace-{conversation_id}", request_id=request_id, ms=ms, **summary)
        return reply
