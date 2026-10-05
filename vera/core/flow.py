"""Conversation flow of a dispute: a state machine over the event log.

The interpreter only reads the message. This code decides the next step with the policy engine, acts only through the
tools port and its action gate, dates deadlines only with the legal clock, and sends no reply that fails the validator.

Conversation is the public face of the flow and runs one turn; its steps live in vera/core/steps, one module per
group, all over the same FlowSupport.
"""

from vera.contracts.common import Language
from vera.contracts.conversation import MessageRequest, MessageResponse, Stage
from vera.contracts.events import Event, EventType
from vera.contracts.handoff import LanguageVariant
from vera.contracts.interpretation import Answer, ClaimType, Interpretation
from vera.core.state import FlowState, Step
from vera.core.steps.actions import ActionSteps
from vera.core.steps.base import INTENT_CLAIMS, MAX_TURNS, VARIANTS, Turn, is_aside, overrides_the_button
from vera.core.steps.blocked import BlockedSteps
from vera.core.steps.charges import ChargeSteps
from vera.core.steps.claim import ClaimSteps
from vera.core.steps.handoff import HandoffSteps
from vera.core.steps.lost_card import LostCardSteps
from vera.core.steps.person import PersonSteps
from vera.core.steps.safety import SafetySteps
from vera.output.render import language_of
from vera.output.validator import UnsafeReplyError, check
from vera.ports.tools import Session

# The five states of the brand for the panel beside the conversation; a step not listed is a verification.
STAGES: dict[Step, Stage] = {
    Step.CHOOSE_CHARGE: "analysis",
    Step.CLARIFY: "analysis",
    Step.CHOOSE_CARD: "analysis",
    Step.HANDED_OFF: "result",
    Step.DONE: "resolved",
}


class Conversation(
    SafetySteps, PersonSteps, ClaimSteps, BlockedSteps, LostCardSteps, ChargeSteps, ActionSteps, HandoffSteps
):
    """One conversation of a dispute: start, reply and history. Each turn runs the steps of vera/core/steps."""

    def start(
        self, session: Session, preferred_language: Language | None = None, first_name: str | None = None
    ) -> MessageResponse:
        """The greeting, by name when the customer has one, and the opening menu."""
        customer = self._tools.customer(session)
        if customer is None:
            raise LookupError("unknown customer")
        variant = LanguageVariant.PT if preferred_language is Language.PT else VARIANTS[customer.country]
        state = FlowState(variant=variant)
        turn = Turn(session, state, None)
        turn.lines.append(self._text(turn, "greeting", who=f", {first_name}" if first_name else ""))
        self._menu(turn)
        return self._finish(turn)

    def reply(
        self, session: Session, message: MessageRequest, security_signals: tuple[str, ...] = ()
    ) -> MessageResponse:
        """One customer turn; security_signals come from the gateway, read on the original text."""
        events = self._log.read(session.conversation_id)
        if not events:
            raise LookupError("unknown conversation")
        asked = next(e for e in reversed(events) if e.type is EventType.REPLY)
        turn = Turn(session, FlowState.model_validate(asked.data["state"]), events[-1], asked=asked)
        turn.decided = {(e.data["rule"], e.data.get("outcome")) for e in events if e.type is EventType.RULE_DECISION}
        turns = 1 + sum(1 for event in events if event.type is EventType.CUSTOMER_MESSAGE)
        self._record(turn, EventType.CUSTOMER_MESSAGE, {"text": message.text, "option": message.selected_option})
        if turns > MAX_TURNS:
            self._turn_limit(turn)
        else:
            self._take_turn(turn, message, security_signals)
        self._alert_fraud_if_due(turn)
        return self._finish(turn)

    def history(self, conversation_id: str) -> tuple[Event, ...]:
        """Events of a conversation, for audit and replay."""
        return self._log.read(conversation_id)

    def _take_turn(self, turn: Turn, message: MessageRequest, security_signals: tuple[str, ...]) -> None:
        turn.typed = message.text is not None
        reading = self._interpret(turn, message, flagged=bool(security_signals))
        if security_signals:
            self._security_event(turn, security_signals)
        if reading.asks_if_human and reading.claim_type is not ClaimType.HUMAN_REQUEST:
            # VERA never passes for a person: it says what it is, offers one, and keeps the open question.
            turn.lines.append(self._text(turn, "not_a_person"))
            self._repeat_question(turn)
            return
        if self._safety_first(turn, reading):
            return
        self._validate_emotion(turn, reading, flagged=bool(security_signals))
        if security_signals:
            # POL-03: the message is data; nothing is searched or changed.
            turn.lines.append(self._text(turn, "not_found"))
            self._repeat_question(turn)
        else:
            self._advance(turn, reading)

    def _interpret(self, turn: Turn, message: MessageRequest, flagged: bool = False) -> Interpretation:
        language = language_of(turn.state.variant)
        if turn.state.step is Step.ASK_CLAIM and turn.state.claim_type is None:
            expecting = "claim"
        elif turn.state.step in (Step.CHOOSE_CHARGE, Step.SWEEP, Step.CHOOSE_CARD, Step.REVIEW):
            expecting = "choice"
        elif turn.state.step is Step.SCAM_DETAILS:
            expecting = "details"
        else:
            expecting = "yes_no"
        if message.text:
            context = {"language": language.value, "expecting": expecting, "question": turn.state.step.value}
            if flagged:
                # The gateway flagged the text: only deterministic rules read it, never a model it could steer.
                context["flagged"] = "yes"
            reading = self._interpreter.interpret(message.text, context)
            provider = self._interpreter.name
            if message.intent and expecting == "claim" and not overrides_the_button(reading):
                # The button the customer pressed is the claim; the text still gives the charge and the safety words.
                reading = reading.model_copy(
                    update={
                        "claim_type": INTENT_CLAIMS[message.intent],
                        "has_card": Answer.NO if message.intent == "lost_card" else reading.has_card,
                        "confidence": 1.0,
                    }
                )
        else:
            option = message.selected_option
            # A reason of the opening menu reads as the claim the customer would have written.
            intent = option if isinstance(option, str) and option in INTENT_CLAIMS else None
            reading = Interpretation(
                claim_type=INTENT_CLAIMS[intent] if intent else turn.state.claim_type or ClaimType.UNRECOGNIZED_CHARGE,
                has_card=Answer.NO if intent == "lost_card" else Answer.NOT_SAID,
                answer=Answer(option) if option in ("yes", "no") else Answer.NOT_SAID,
                selected_numbers=(option,) if isinstance(option, int) else (),
                language=language,
                confidence=1.0,
            )
            provider = "option"
        self._record(turn, EventType.INTERPRETATION, reading.model_dump(mode="json"), provider)
        if reading.language is Language.PT and turn.state.variant is not LanguageVariant.PT:
            turn.state = turn.state.advance(variant=LanguageVariant.PT)
        return reading

    def _advance(self, turn: Turn, reading: Interpretation) -> None:
        # At the POL-01 offer or the key questions of a scam, a message on the side still leads to the person.
        if turn.state.step not in (Step.ASK_CLAIM, Step.PERSON_OFFERED, Step.SCAM_DETAILS) and is_aside(reading):
            self._answer_aside(turn, reading)
            return
        handlers = {
            Step.ASK_CLAIM: self._on_claim,
            Step.CHOOSE_CHARGE: self._on_choice,
            Step.CLARIFY: self._on_clarify,
            Step.ASK_CHANNEL: self._on_channel,
            Step.ASK_CARD: self._on_card,
            Step.SWEEP: self._on_sweep,
            Step.CONFIRM_BLOCK: self._on_block,
            Step.CONFIRM_REGISTER: self._on_register,
            Step.CONFIRM_PERSON: self._on_person,
            Step.PERSON_OFFERED: self._on_person_offer,
            Step.SCAM_DETAILS: self._on_scam_details,
            Step.CHOOSE_CARD: self._on_choose_card,
            Step.REVIEW: self._on_review,
            Step.BLOCKED_OFFER: self._on_blocked_offer,
        }
        handler = handlers.get(turn.state.step)
        if handler is None:
            self._after_the_end(turn, reading)
            return
        handler(turn, reading)

    def _finish(self, turn: Turn) -> MessageResponse:
        text = "\n\n".join(turn.lines)
        previous = turn.asked.data.get("text") if turn.asked else None
        if text == previous and turn.state.step not in (Step.DONE, Step.HANDED_OFF):
            # The same words twice in a row read as a machine stuck: the reply is introduced differently.
            text = f"{self._text(turn, 'rephrase', pick=turn.state.attempts)} {text}"
        try:
            text = check(text, frozenset(turn.amounts))
        except UnsafeReplyError as error:
            self._record(turn, EventType.RULE_DECISION, {"rule": "output_validator", "violations": error.violations})
            text = self._text(turn, "tool_failure")
            turn.state = turn.state.advance(step=Step.HANDED_OFF, escalated=True)
            turn.options.clear()
        response = MessageResponse(
            reply=text,
            options=tuple(turn.options),
            multiple_choice=turn.multiple_choice,
            pending_confirmation=turn.pending,
            glass_box=tuple(turn.glass_box),
            stage=_stage(turn.state),
            charge=self._charge_in_question(turn),
            case_id=turn.state.case_id,
        )
        self._record(
            turn,
            EventType.REPLY,
            {
                "text": text,
                "options": [o.model_dump(mode="json") for o in turn.options],
                "pending": turn.pending.model_dump(mode="json") if turn.pending else None,
                "state": turn.state.model_dump(mode="json"),
            },
        )
        return response


def _stage(state: FlowState) -> Stage:
    if state.step is Step.ASK_CLAIM:
        return "analysis" if state.claim_type else "received"
    return STAGES.get(state.step, "verification")
