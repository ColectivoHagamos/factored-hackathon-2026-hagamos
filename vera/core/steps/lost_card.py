"""A lost or stolen card: it is protected before anything else (POL-06), then its recent movements are reviewed."""

from datetime import timedelta

from vera.contracts.charges import ChargeKind
from vera.contracts.conversation import Option
from vera.contracts.handoff import Queue, TransferReason
from vera.contracts.interpretation import Answer, Interpretation
from vera.contracts.tools import SearchChargesInput, ToolError
from vera.core.state import Step
from vera.core.steps.base import REVIEW_LIMIT, SEARCH_DAYS, FlowSupport, Turn, no_results
from vera.policy.engine import Outcome, Signal


class LostCardSteps(FlowSupport):
    """Protecting a lost or stolen card, then reviewing its movements."""

    def _protect_first(self, turn: Turn) -> None:
        """POL-06: the card is protected before anything else, and its recent movements are reviewed afterwards."""
        turn.lines.append(self._text(turn, "lost_card_empathy"))
        today = self._now().date()
        args = SearchChargesInput(
            date_from=today - timedelta(days=SEARCH_DAYS[ChargeKind.PURCHASE]), date_to=today, kind=ChargeKind.PURCHASE
        )
        result = self._tools.search_charges(turn.session, self._offers(turn), args)
        self._record_tool(turn, "search_charges", args.model_dump(mode="json"), result)
        if no_results(result):
            # No recent purchase names the card: a person of the Fraud team protects it.
            turn.lines.append(self._text(turn, "lost_card_no_movements"))
            self._hand_off(turn, Queue.FRAUD, TransferReason.LOST_CARD)
            return
        if isinstance(result, ToolError):
            self._fail(turn)
            return
        output, offers = result
        turn.state = turn.state.advance(
            charges_offered=offers.charges, cards_offered=offers.cards, review_after_block=True, attempts=0
        )
        cards = {c.card_n: c.card or "" for c in output.candidates if c.card_n is not None}
        if len(cards) > 1:
            turn.lines.append(self._text(turn, "choose_card"))
            turn.options.extend(Option(n=n, label=label) for n, label in sorted(cards.items()))
            turn.state = turn.state.advance(step=Step.CHOOSE_CARD)
            return
        if not cards:
            self._review_movements(turn)
            return
        card_n, card = next(iter(cards.items()))
        self._protect_card(turn, card_n, card)

    def _on_choose_card(self, turn: Turn, reading: Interpretation) -> None:
        chosen = [n for n in reading.selected_numbers if n in turn.state.cards_offered]
        if not chosen:
            self._ask_again(turn, "choose_card", step=Step.CHOOSE_CARD)
            return
        shown = {o["n"]: o["label"] for o in (turn.asked.data.get("options", []) if turn.asked else [])}
        self._protect_card(turn, chosen[0], shown.get(chosen[0], ""))

    def _protect_card(self, turn: Turn, card_n: int, card: str) -> None:
        turn.state = turn.state.advance(signals=[Signal.CARD_NOT_IN_POSSESSION])
        evaluation = self._evaluate(turn, self._dispute_facts(turn, []))
        on_request = Outcome.BLOCK_ON_CUSTOMER_REQUEST in evaluation.outcomes
        self._propose_block(turn, card_n, card, "lost_card_block_on_request" if on_request else "lost_card_block")

    def _review_movements(self, turn: Turn) -> None:
        """Once the card is protected, the recent movements: the customer marks the ones they did not make."""
        recent = sorted(turn.state.charges_offered)[:REVIEW_LIMIT]
        details = [d for d in (self._detail(turn, n) for n in recent) if d is not None]
        turn.lines.append(self._text(turn, "review_movements"))
        turn.options.extend(Option(n=d.n, label=self._receipt(turn, d)) for d in details)
        turn.multiple_choice = True
        turn.state = turn.state.advance(
            step=Step.REVIEW, swept=[d.n for d in details], review_after_block=False, chosen=None
        )

    def _on_review(self, turn: Turn, reading: Interpretation) -> None:
        offered = set(turn.state.swept)
        if reading.selected_numbers:
            unrecognized = [n for n in reading.selected_numbers if n in offered]
        elif reading.answer is Answer.NO:
            unrecognized = sorted(offered)
        else:
            unrecognized = []
        if not unrecognized:
            # As in the sweep, «todos» means the customer recognizes every movement shown.
            turn.lines.append(self._text(turn, "recognized_all"))
            turn.lines.append(self._text(turn, "closing"))
            turn.state = turn.state.advance(step=Step.DONE)
            return
        self._assess_signals(turn, unrecognized, offer_block=False)
