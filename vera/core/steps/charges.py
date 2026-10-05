"""The charge in question: the search, the choice among candidates, how it was bought, the card, and the sweep of
other charges with the signals they raise."""

from datetime import timedelta

from vera.contracts.charges import ChargeKind, ChargeStatus, FraudScoreBand
from vera.contracts.conversation import Option
from vera.contracts.interpretation import Answer, ClaimType, DeclaredChannel, Interpretation
from vera.contracts.tools import SearchChargesInput, SweepChargesInput, ToolError, ToolErrorCode, ViewChargeInput
from vera.core.state import Step
from vera.core.steps.base import NAMED_SEARCH_DAYS, SEARCH_DAYS, FlowSupport, Turn, no_results
from vera.policy.engine import Facts, Outcome, Signal


class ChargeSteps(FlowSupport):
    """Finding the charge in question and what the customer knows about it."""

    def _search(self, turn: Turn, reading: Interpretation, kind: ChargeKind) -> None:
        today = self._now().date()
        named = reading.amount is not None or reading.merchant_text is not None
        args = SearchChargesInput(
            date_from=today - timedelta(days=NAMED_SEARCH_DAYS if named else SEARCH_DAYS[kind]),
            date_to=today,
            amount=reading.amount,
            merchant=reading.merchant_text,
            kind=kind,
        )
        result = self._tools.search_charges(turn.session, self._offers(turn), args)
        self._record_tool(turn, "search_charges", args.model_dump(mode="json"), result)
        missed = no_results(result) and reading.merchant_text is not None
        if missed:
            # The merchant written by the customer may not match the statement; try the recent window without it.
            args = args.model_copy(update={"merchant": None, "date_from": today - timedelta(days=SEARCH_DAYS[kind])})
            result = self._tools.search_charges(turn.session, self._offers(turn), args)
            self._record_tool(turn, "search_charges", args.model_dump(mode="json"), result)
        if no_results(result):
            # The customer already gave an amount: VERA asks for what is still missing, not for it again.
            self._ask_again(turn, "ask_detail" if reading.amount is None else "ask_detail_amount")
            return
        if isinstance(result, ToolError):
            self._fail(turn)
            return
        output, offers = result
        turn.state = turn.state.advance(charges_offered=offers.charges, cards_offered=offers.cards, attempts=0)
        # AC-2: a charge other than the one named is never presented as the one in question; the customer chooses.
        if len(output.candidates) == 1 and not missed:
            self._clarify(turn, output.candidates[0].n)
            return
        self._evaluate(turn, Facts(account_country=self._country(turn), candidates_found=len(output.candidates)))
        turn.lines.append(self._text(turn, "named_not_found" if missed else "choose_charge"))
        turn.options.extend(Option(n=c.n, label=self._receipt(turn, c)) for c in output.candidates)
        turn.state = turn.state.advance(step=Step.CHOOSE_CHARGE)

    def _on_choice(self, turn: Turn, reading: Interpretation) -> None:
        offered = [n for n in reading.selected_numbers if n in turn.state.charges_offered]
        if not offered:
            self._ask_again(turn, "choose_charge", step=Step.CHOOSE_CHARGE)
            return
        self._clarify(turn, offered[0], chosen=True)

    def _clarify(self, turn: Turn, n: int, chosen: bool = False) -> None:
        """The charge in question, named as a person names it; a charge the customer just chose is not read back."""
        detail = self._tools.view_charge(turn.session, self._offers(turn), ViewChargeInput(candidate_n=n))
        self._record_tool(turn, "view_charge", {"candidate_n": n}, detail)
        if isinstance(detail, ToolError):
            self._fail(turn)
            return
        lead = "clarify_chosen" if chosen else "clarify_found"
        turn.lines.append(self._text(turn, lead, charge=self._reference(turn, detail)))
        explained = detail.status is not ChargeStatus.APPROVED or detail.is_known_merchant
        if detail.status is not ChargeStatus.APPROVED:
            self._evaluate(turn, Facts(account_country=self._country(turn), charge_status=detail.status))
            turn.lines.append(self._text(turn, f"status_{detail.status.value}"))
        if detail.is_known_merchant:
            turn.lines.append(self._text(turn, "known_merchant"))
        if turn.state.claim_type is ClaimType.IMPROPER_CHARGE:
            question = "ask_is_this_charge"
        else:
            # With nothing new to show, the question says why it is asked, so it does not read as doubt.
            question = "ask_recognize" if explained else "ask_recognize_hint"
        turn.lines.append(self._text(turn, question))
        self._yes_no(turn)
        turn.state = turn.state.advance(step=Step.CLARIFY, chosen=n, disputed=[n])

    def _on_clarify(self, turn: Turn, reading: Interpretation) -> None:
        if turn.state.claim_type is ClaimType.IMPROPER_CHARGE:
            if reading.answer is Answer.YES:
                self._propose_registration(turn)
            else:
                self._ask_again(turn, "ask_detail", step=Step.ASK_CLAIM)
            return
        if reading.answer is Answer.YES:
            turn.lines.append(self._text(turn, "recognized"))
            turn.lines.append(self._text(turn, "closing"))
            turn.state = turn.state.advance(step=Step.DONE)
            return
        if reading.answer is Answer.NOT_SAID:
            self._ask_again(turn, "ask_recognize_again", step=Step.CLARIFY)
            return
        if turn.state.declared_channel is None:
            turn.lines.append(self._text(turn, "ask_channel"))
            self._yes_no(turn)
            turn.options.append(Option(n=3, label=self._text(turn, "not_sure"), answer="not_sure"))
            turn.state = turn.state.advance(step=Step.ASK_CHANNEL)
            return
        self._ask_card_or_sweep(turn)

    def _on_channel(self, turn: Turn, reading: Interpretation) -> None:
        channel = reading.declared_channel or {
            Answer.YES: DeclaredChannel.ONLINE,
            Answer.NO: DeclaredChannel.IN_PERSON,
        }.get(reading.answer, DeclaredChannel.UNKNOWN)
        turn.state = turn.state.advance(declared_channel=channel)
        self._ask_card_or_sweep(turn)

    def _ask_card_or_sweep(self, turn: Turn) -> None:
        if turn.state.has_card is Answer.NOT_SAID:
            turn.lines.append(self._text(turn, "ask_card"))
            self._yes_no(turn)
            turn.state = turn.state.advance(step=Step.ASK_CARD)
            return
        self._sweep(turn)

    def _on_card(self, turn: Turn, reading: Interpretation) -> None:
        answer = reading.has_card if reading.has_card is not Answer.NOT_SAID else reading.answer
        turn.state = turn.state.advance(has_card=answer)
        self._sweep(turn)

    def _sweep(self, turn: Turn) -> None:
        result = self._tools.sweep_charges(
            turn.session, self._offers(turn), SweepChargesInput(candidate_n=turn.state.chosen)
        )
        self._record_tool(turn, "sweep_charges", {"candidate_n": turn.state.chosen}, result)
        if isinstance(result, ToolError) and result.code is ToolErrorCode.FAILURE:
            self._fail(turn)
            return
        if isinstance(result, ToolError):
            self._assess_signals(turn, unrecognized=[])
            return
        output, offers = result
        turn.state = turn.state.advance(charges_offered=offers.charges, cards_offered=offers.cards)
        others = [c for c in output.charges if c.n != turn.state.chosen]
        if not others:
            self._assess_signals(turn, unrecognized=[])
            return
        turn.lines.append(self._text(turn, "sweep"))
        turn.options.extend(Option(n=c.n, label=self._receipt(turn, c)) for c in others)
        turn.multiple_choice = True
        turn.state = turn.state.advance(step=Step.SWEEP, swept=[c.n for c in others])

    def _on_sweep(self, turn: Turn, reading: Interpretation) -> None:
        # Only the charges shown in the sweep can be disowned here, never others listed earlier (AC-2).
        offered = set(turn.state.swept)
        if reading.selected_numbers:
            unrecognized = [n for n in reading.selected_numbers if n in offered]
        elif reading.answer is Answer.NO:
            unrecognized = sorted(offered)
        else:
            unrecognized = []
        self._assess_signals(turn, unrecognized)

    def _assess_signals(self, turn: Turn, unrecognized: list[int], offer_block: bool = True) -> None:
        details = [self._detail(turn, n) for n in [turn.state.chosen, *unrecognized]]
        details = [d for d in details if d is not None]
        signals: set[Signal] = set()
        if turn.state.has_card is Answer.NO:
            signals.add(Signal.CARD_NOT_IN_POSSESSION)
        if len(details) >= self._engine.parameters.unrecognized_charges_signal:
            signals.add(Signal.MULTIPLE_UNRECOGNIZED)
        if any(d.fraud_score_band is FraudScoreBand.ABOVE_30 for d in details):
            signals.add(Signal.FRAUD_SCORE_ABOVE_THRESHOLD)
        if any(d.status is not ChargeStatus.APPROVED for d in details):
            signals.add(Signal.UNRECOGNIZED_NON_APPROVED)
        if any(not d.is_known_merchant for d in details):
            signals.add(Signal.NEW_MERCHANT)
        disputed = [d.n for d in details if d.status in (ChargeStatus.APPROVED, ChargeStatus.PENDING)]
        turn.state = turn.state.advance(signals=sorted(signals), disputed=disputed)
        evaluation = self._evaluate(turn, self._dispute_facts(turn, details))
        if Outcome.FRAUD_ALERT in evaluation.outcomes:
            turn.state = turn.state.advance(fraud_alert_charges=[d.n for d in details])
        card_n = details[0].card_n if details and offer_block else None
        if Outcome.OFFER_BLOCK in evaluation.outcomes and card_n:
            self._propose_block(turn, card_n, details[0].card, "offer_block")
        elif Outcome.BLOCK_ON_CUSTOMER_REQUEST in evaluation.outcomes and card_n:
            self._propose_block(turn, card_n, details[0].card, "block_on_request")
        else:
            self._propose_registration(turn)
