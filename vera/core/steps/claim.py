"""The opening: the claim, read from the customer's words or the button pressed, the menu of what VERA covers, and
the key questions of a scam (POL-10)."""

from vera.contracts.charges import ChargeKind
from vera.contracts.conversation import Option
from vera.contracts.handoff import Queue, TransferReason
from vera.contracts.interpretation import Answer, ClaimType, Interpretation
from vera.core.state import Step
from vera.core.steps.base import MENU, FlowSupport, Turn
from vera.policy.engine import Facts, Outcome


class ClaimSteps(FlowSupport):
    """The opening of the conversation and the claim."""

    def _on_claim(self, turn: Turn, reading: Interpretation) -> None:
        if turn.state.claim_type is not None:
            # The claim is known and VERA asked for a detail: this message only narrows the search.
            known = turn.state.claim_type is ClaimType.IMPROPER_CHARGE and not turn.state.duplicate
            self._search(turn, reading, ChargeKind.BANK_ADJUSTMENT if known else ChargeKind.PURCHASE)
            return
        if reading.duplicate and reading.claim_type in (ClaimType.IMPROPER_CHARGE, ClaimType.UNRECOGNIZED_CHARGE):
            # A purchase charged twice is an improper charge whatever the reader called it; the purchase is known.
            reading = reading.model_copy(update={"claim_type": ClaimType.IMPROPER_CHARGE})
        sure = reading.confidence >= self._engine.parameters.interpreter_min_confidence
        if reading.greeting and (reading.claim_type is ClaimType.OUT_OF_SCOPE or not sure):
            # A greeting, small talk or a plea for help: warm words and the menu, never a question about a charge.
            self._welcome(turn, "welcome")
            return
        customer = self._tools.customer(turn.session)
        evaluation = self._evaluate(
            turn,
            Facts(
                account_country=customer.country,
                claim_type=reading.claim_type,
                interpreter_confidence=reading.confidence,
                pix_mentioned=reading.pix_mentioned,
                already_escalated=turn.state.escalated,
            ),
        )
        if Outcome.OUT_OF_SCOPE in evaluation.outcomes:
            turn.lines.append(self._text(turn, "pix"))
            self._menu(turn)
            return
        if reading.claim_type is ClaimType.OUT_OF_SCOPE:
            self._welcome(turn, "out_of_scope_opening")
            return
        if Outcome.ASK_INSTEAD_OF_ACT in evaluation.outcomes:
            self._ask_again(turn, "low_confidence")
            return
        if reading.claim_type is ClaimType.SCAM_TRANSFER:
            turn.state = turn.state.advance(
                claim_type=reading.claim_type, authorized_payment=reading.authorized_payment
            )
            if reading.date_text and reading.contact_channel:
                # The customer already said when and how: nothing to ask again.
                self._on_scam_details(turn, reading)
                return
            turn.lines.append(self._text(turn, "scam"))
            turn.state = turn.state.advance(
                step=Step.SCAM_DETAILS, date_text=reading.date_text, contacted_by=reading.contact_channel
            )
            return
        duplicate = reading.duplicate and reading.claim_type is ClaimType.IMPROPER_CHARGE
        improper = reading.claim_type is ClaimType.IMPROPER_CHARGE and not duplicate
        kind = ChargeKind.BANK_ADJUSTMENT if improper else ChargeKind.PURCHASE
        turn.state = turn.state.advance(
            claim_type=reading.claim_type, declared_channel=reading.declared_channel, duplicate=duplicate
        )
        if reading.has_card is not Answer.NOT_SAID:
            turn.state = turn.state.advance(has_card=reading.has_card)
        if kind is ChargeKind.PURCHASE and turn.state.has_card is Answer.NO and not duplicate:
            self._protect_first(turn)
            return
        turn.lines.append(self._text(turn, "duplicate" if duplicate else "improper" if improper else "empathy"))
        self._search(turn, reading, kind)

    def _welcome(self, turn: Turn, template: str) -> None:
        """At the opening, warm words that change each time they come back, and the menu of what VERA covers."""
        turn.lines.append(self._text(turn, template, pick=turn.state.nudges))
        self._menu(turn)
        turn.state = turn.state.advance(nudges=turn.state.nudges + 1)

    def _menu(self, turn: Turn) -> None:
        turn.options.extend(
            Option(n=n, label=self._text(turn, label), answer=intent) for n, (intent, label) in enumerate(MENU, 1)
        )

    def _on_scam_details(self, turn: Turn, reading: Interpretation) -> None:
        """POL-10: whatever the answer, Fraud gets it with the case, and a transfer has no chargeback to promise."""
        turn.state = turn.state.advance(
            date_text=reading.date_text or turn.state.date_text,
            contacted_by=reading.contact_channel or turn.state.contacted_by,
        )
        turn.lines.append(self._text(turn, "scam_handoff"))
        self._hand_off(turn, Queue.FRAUD, TransferReason.SCAM_TRANSFER)
