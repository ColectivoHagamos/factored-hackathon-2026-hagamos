"""Safety first: a person, a threat or the regulator win over any step (POL-01, POL-02, POL-09), and a message
flagged as an injection acts on nothing (POL-03)."""

from vera.contracts.events import EventType
from vera.contracts.handoff import Queue, TransferReason
from vera.contracts.interpretation import ClaimType, Interpretation
from vera.core.state import FlowState, Step
from vera.core.steps.base import MAX_TURNS, FlowSupport, Turn, venue_of
from vera.policy.engine import Facts, Outcome


class SafetySteps(FlowSupport):
    """What wins over any step: a person, a threat, the regulator, an injection and the turn limit."""

    def _safety_first(self, turn: Turn, reading: Interpretation) -> bool:
        """POL-01, POL-02 and POL-09 win over every other step."""
        customer = self._tools.customer(turn.session)
        # During the key questions of a scam a person is already on the way (POL-10), and at a block VERA itself
        # offered the person: there the request needs no offer.
        person = reading.claim_type is ClaimType.HUMAN_REQUEST and turn.state.step not in (
            Step.SCAM_DETAILS,
            Step.BLOCKED_OFFER,
        )
        sure = reading.confidence >= self._engine.parameters.interpreter_min_confidence
        if person and not sure and turn.state.step not in (Step.HANDED_OFF, Step.PERSON_OFFERED):
            # POL-14 before POL-01: when the reading is unsure, VERA asks before treating it as a request.
            turn.lines.append(self._text(turn, "offer_person"))
            self._yes_no(turn)
            turn.state = turn.state.advance(step=Step.CONFIRM_PERSON, resume_step=self._open_question(turn))
            return True
        facts = Facts(
            account_country=customer.country,
            human_requested=person,
            person_offers_made=turn.state.person_offers,
            coercion=reading.coercion,
            regulator_mentioned=reading.regulator_mentioned,
            already_escalated=turn.state.escalated,
        )
        evaluation = self._evaluate(turn, facts)
        if turn.state.step is Step.HANDED_OFF:
            return False
        if not ({Outcome.HANDOFF, Outcome.INFORM_VENUE} & evaluation.outcomes):
            # POL-01 alone: one offer to go on first. Coercion and the regulator never wait for an offer.
            if Outcome.OFFER_BEFORE_TRANSFER in evaluation.outcomes:
                self._offer_before_transfer(turn)
                return True
            return False
        if reading.coercion:
            turn.lines.append(self._text(turn, "safety"))
            reason = TransferReason.COERCION
        elif Outcome.INFORM_VENUE in evaluation.outcomes:
            turn.lines.append(self._text(turn, "regulator", venue=venue_of(customer.country)))
            reason = TransferReason.REGULATOR
        else:
            turn.lines.append(self._text(turn, "handoff_now"))
            reason = TransferReason.PERSON_REQUESTED
        self._hand_off(turn, evaluation.queue or Queue.COMPLAINTS, reason)
        return True

    def _validate_emotion(self, turn: Turn, reading: Interpretation, flagged: bool) -> None:
        """Worry, fear or anger is acknowledged before the next step, in words that change each time.

        A clear claim in the first message is answered by its own empathy, so it is not acknowledged twice."""
        sure = reading.confidence >= self._engine.parameters.interpreter_min_confidence
        opening_claim = (
            turn.state.step is Step.ASK_CLAIM
            and turn.state.claim_type is None
            and sure
            and not reading.greeting
            and reading.claim_type is not ClaimType.OUT_OF_SCOPE
        )
        if not reading.distress or flagged or opening_claim:
            return
        turn.lines.append(self._text(turn, "calm", pick=turn.state.calmed))
        turn.state = turn.state.advance(calmed=turn.state.calmed + 1)

    def _security_event(self, turn: Turn, signals: tuple[str, ...]) -> None:
        """POL-03: every attempt is recorded with its signals, also when a person takes over."""
        facts = Facts(
            account_country=self._country(turn),
            instruction_in_message=any(s != "other_customer" for s in signals),
            foreign_charge_requested="other_customer" in signals,
            already_escalated=turn.state.escalated,
        )
        self._evaluate(turn, facts)
        self._record(turn, EventType.SECURITY_EVENT, {"rule": "POL-03", "signals": [*signals]})

    def _turn_limit(self, turn: Turn) -> None:
        """LLM10: past the limit nothing more is interpreted and the conversation goes to a person once."""
        if turn.state.step is not Step.HANDED_OFF:
            self._record(turn, EventType.RULE_DECISION, {"rule": "turn_limit", "turns": MAX_TURNS})
            self._hand_off(turn, turn.state.queue or Queue.COMPLAINTS, TransferReason.TURN_LIMIT)
        turn.lines.append(self._text(turn, "turn_limit"))

    def _answer_aside(self, turn: Turn, reading: Interpretation) -> None:
        """What VERA does not cover is said and oriented (POL-15 for Pix); the open question stays open."""
        evaluation = self._evaluate(
            turn, Facts(account_country=self._country(turn), pix_mentioned=reading.pix_mentioned)
        )
        turn.lines.append(self._text(turn, "pix" if Outcome.OUT_OF_SCOPE in evaluation.outcomes else "out_of_scope"))
        self._repeat_question(turn)

    def _after_the_end(self, turn: Turn, reading: Interpretation) -> None:
        """A message after the end: with a person on the way VERA says so; after a closing, a new reason starts over."""
        sure = reading.confidence >= self._engine.parameters.interpreter_min_confidence
        new_claim = sure and not reading.greeting and reading.claim_type is not ClaimType.OUT_OF_SCOPE
        if turn.state.step is Step.DONE and new_claim:
            turn.state = FlowState(variant=turn.state.variant)
            self._on_claim(turn, reading)
            return
        template = "after_handoff" if turn.state.step is Step.HANDED_OFF else "after_done"
        turn.lines.append(self._text(turn, template, pick=turn.state.nudges))
        if template == "after_done":
            self._menu(turn)
        turn.state = turn.state.advance(nudges=turn.state.nudges + 1)
