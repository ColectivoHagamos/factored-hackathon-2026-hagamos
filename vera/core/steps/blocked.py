"""A payment declined or a card blocked by the bank: VERA shows the declined attempts it reads in the movements, says
it cannot see the reason or unblock, and offers the person of the Fraud team who can."""

from datetime import timedelta

from vera.contracts.charges import ChargeKind, ChargeStatus
from vera.contracts.handoff import Queue, TransferReason
from vera.contracts.interpretation import Answer, ClaimType, Interpretation
from vera.contracts.tools import SearchChargesInput, ToolError
from vera.core.state import Step
from vera.core.steps.base import SEARCH_DAYS, FlowSupport, Turn

# The declined attempts shown at most: the latest ones, enough to recognize the payment that failed.
DECLINED_SHOWN = 3


class BlockedSteps(FlowSupport):
    """A declined payment or a blocked card, and the offer of the person who can review it."""

    def _blocked(self, turn: Turn) -> None:
        turn.lines.append(self._text(turn, "blocked"))
        today = self._now().date()
        args = SearchChargesInput(
            date_from=today - timedelta(days=SEARCH_DAYS[ChargeKind.PURCHASE]), date_to=today, kind=ChargeKind.PURCHASE
        )
        result = self._tools.search_charges(turn.session, self._offers(turn), args)
        self._record_tool(turn, "search_charges", args.model_dump(mode="json"), result)
        declined = []
        if not isinstance(result, ToolError):
            output, offers = result
            declined = [c for c in output.candidates if c.status is ChargeStatus.DECLINED][-DECLINED_SHOWN:]
            # The attempts go with the transfer note, so the analyst does not ask for them again.
            turn.state = turn.state.advance(
                charges_offered=offers.charges, cards_offered=offers.cards, disputed=[c.n for c in declined]
            )
        if declined:
            turn.lines.append(self._text(turn, "blocked_attempts"))
            turn.lines.append("\n".join(f"• {self._receipt(turn, c)}" for c in declined))
        else:
            turn.lines.append(self._text(turn, "blocked_none"))
        turn.lines.append(self._text(turn, "blocked_offer"))
        self._yes_no(turn)
        turn.state = turn.state.advance(step=Step.BLOCKED_OFFER)

    def _on_blocked_offer(self, turn: Turn, reading: Interpretation) -> None:
        sure = reading.confidence >= self._engine.parameters.interpreter_min_confidence
        # A language model fills a claim type even for a bare "no": only a message that names a charge, or says more
        # than yes or no, moves on to a claim.
        names_a_charge = reading.merchant_text is not None or reading.amount is not None
        tells_a_claim = (
            turn.typed
            and sure
            and not reading.greeting
            and reading.claim_type is not ClaimType.OUT_OF_SCOPE
            and (reading.answer is Answer.NOT_SAID or names_a_charge)
        )
        if reading.answer is Answer.YES or reading.claim_type is ClaimType.HUMAN_REQUEST:
            turn.lines.append(self._text(turn, "blocked_handoff"))
            self._hand_off(turn, Queue.FRAUD, TransferReason.PERSON_REQUESTED)
        elif tells_a_claim:
            # A claim written in so many words, even one that starts with "no": VERA goes on with it.
            turn.state = turn.state.advance(step=Step.ASK_CLAIM, disputed=[])
            self._on_claim(turn, reading)
        elif reading.answer is Answer.NO:
            turn.lines.append(self._text(turn, "blocked_declined"))
            self._menu(turn)
            turn.state = turn.state.advance(step=Step.ASK_CLAIM, disputed=[])
        else:
            self._ask_again(turn, "confirm_options", step=Step.BLOCKED_OFFER)
