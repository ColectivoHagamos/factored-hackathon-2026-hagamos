"""A person requested: one offer to go on first (POL-01), the check of an unsure reading (POL-14) and the way back to
the question that was open."""

from vera.contracts.events import EventType
from vera.contracts.handoff import Queue, TransferReason
from vera.contracts.interpretation import Answer, ClaimType, Interpretation
from vera.core.state import Step
from vera.core.steps.base import FlowSupport, Turn
from vera.policy.engine import Facts, Outcome


class PersonSteps(FlowSupport):
    """The detour when the customer asks for a person, and the way back to the open question."""

    def _person_requested(self, turn: Turn) -> None:
        """POL-01 once the request is clear: an offer while one is due, then a person with what is already known."""
        facts = Facts(
            account_country=self._country(turn),
            human_requested=True,
            person_offers_made=turn.state.person_offers,
            already_escalated=turn.state.escalated,
        )
        evaluation = self._evaluate(turn, facts)
        if Outcome.OFFER_BEFORE_TRANSFER in evaluation.outcomes:
            self._offer_before_transfer(turn)
            return
        turn.lines.append(self._text(turn, "handoff_now"))
        self._hand_off(turn, evaluation.queue or Queue.COMPLAINTS, TransferReason.PERSON_REQUESTED)

    def _offer_before_transfer(self, turn: Turn) -> None:
        """POL-01 (v1.5): VERA offers to review the case first; nothing runs while the offer is open."""
        turn.lines.append(self._text(turn, "offer_before_transfer"))
        self._yes_no(turn)
        turn.state = turn.state.advance(
            step=Step.PERSON_OFFERED,
            resume_step=self._open_question(turn),
            person_offers=turn.state.person_offers + 1,
        )

    def _on_person_offer(self, turn: Turn, reading: Interpretation) -> None:
        sure = reading.confidence >= self._engine.parameters.interpreter_min_confidence
        # A claim written in so many words takes the offer, even when it starts with "no": VERA goes on with it.
        tells_what_happened = (
            turn.typed
            and sure
            and not reading.greeting
            and reading.claim_type not in (ClaimType.HUMAN_REQUEST, ClaimType.OUT_OF_SCOPE)
            and self._open_question(turn) is Step.ASK_CLAIM
        )
        if tells_what_happened:
            turn.state = turn.state.advance(step=Step.ASK_CLAIM, resume_step=None)
            self._on_claim(turn, reading)
        elif reading.answer is Answer.YES:
            self._resume(turn)
        else:
            # The customer insists, or does not take the offer.
            self._person_requested(turn)

    def _on_person(self, turn: Turn, reading: Interpretation) -> None:
        """POL-14: the customer says whether the unsure reading was a request for a person."""
        if reading.answer is Answer.YES:
            self._person_requested(turn)
        elif reading.answer is Answer.NO:
            self._resume(turn)
        else:
            # Neither yes nor no: the message answers the question that was open before.
            turn.state = turn.state.advance(step=self._open_question(turn), resume_step=None)
            self._advance(turn, reading)

    def _open_question(self, turn: Turn) -> Step:
        """The step of the question the customer was answering before a detour about a person."""
        return turn.state.resume_step or turn.state.step

    def _resume(self, turn: Turn) -> None:
        """Back to the open question with its options and attempts; a pending action needs a new yes."""
        step = self._open_question(turn)
        replies = [e for e in self._log.read(turn.session.conversation_id) if e.type is EventType.REPLY]
        turn.asked = next((e for e in reversed(replies) if e.data["state"]["step"] == step.value), None)
        attempts = turn.asked.data["state"]["attempts"] if turn.asked else 0
        turn.state = turn.state.advance(step=step, resume_step=None, attempts=attempts)
        self._repeat_question(turn)
