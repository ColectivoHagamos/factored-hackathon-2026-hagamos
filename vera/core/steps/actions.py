"""Actions on the customer's yes: blocking a card and registering the dispute, each read back, and the closing of a
case with the deadlines of the legal clock."""

from vera.contracts.cases import Case, DisputeReason
from vera.contracts.charges import ChargeStatus, FraudScoreBand
from vera.contracts.conversation import GlassBoxEntry, PendingConfirmation
from vera.contracts.events import EventType
from vera.contracts.handoff import DeclaredFacts, GoodwillCandidate, GoodwillCriterion, LanguageVariant, Queue, Sweep
from vera.contracts.interpretation import Answer, ClaimType, DeclaredChannel, Interpretation
from vera.contracts.tools import (
    BlockCardInput,
    CreateHandoffInput,
    ReadCaseInput,
    RegisterDisputeInput,
    RegisterDisputeOutput,
    ToolError,
)
from vera.core.legal_route import LegalAssessment, assess
from vera.core.state import Step
from vera.core.steps.base import PENDING_TOKEN, FlowSupport, Turn, aware, charges_text, exposure_of
from vera.output.handoff import CARD_LAST_SEEN, build_handoff
from vera.output.render import day, language_of
from vera.policy.engine import Outcome, Signal


class ActionSteps(FlowSupport):
    """The writes a yes unlocks, each read back, and the closing of a case."""

    def _propose_block(self, turn: Turn, card_n: int, card: str | None, template: str) -> None:
        args = BlockCardInput(card_n=card_n, confirmation_token=PENDING_TOKEN)
        confirmation = self._tools.confirm(turn.session, "block_card", args)
        args = args.model_copy(update={"confirmation_token": confirmation.token})
        turn.lines.append(self._text(turn, template, card=card or ""))
        self._yes_no(turn)
        turn.pending = PendingConfirmation(
            action="block_card", summary=card or "card", expires_at=aware(confirmation.expires_at)
        )
        turn.state = turn.state.advance(
            step=Step.CONFIRM_BLOCK, pending_tool="block_card", pending_arguments=args.model_dump(mode="json")
        )

    def _on_block(self, turn: Turn, reading: Interpretation) -> None:
        if reading.answer is Answer.YES:
            args = BlockCardInput.model_validate(turn.state.pending_arguments)
            result = self._tools.block_card(turn.session, self._offers(turn), args)
            self._record_write(turn, "block_card", args, result.output, result.read_back_matches)
            if not result.read_back_matches:
                self._fail(turn)
                return
            pending = (turn.asked.data.get("pending") or {}) if turn.asked else {}
            card = next((c for c in self._case_cards(turn)), pending.get("summary", ""))
            turn.lines.append(self._text(turn, "block_done", card=card))
        elif reading.answer is Answer.NO:
            turn.lines.append(self._text(turn, "block_skipped"))
        else:
            self._ask_again(turn, "confirm_options", step=Step.CONFIRM_BLOCK)
            return
        if turn.state.review_after_block:
            self._review_movements(turn)
            return
        self._propose_registration(turn)

    def _propose_registration(self, turn: Turn) -> None:
        details = [d for d in (self._detail(turn, n) for n in turn.state.disputed) if d is not None]
        approved = [d for d in details if d.status is ChargeStatus.APPROVED]
        if not approved:
            turn.lines.append(self._text(turn, "closing"))
            turn.state = turn.state.advance(step=Step.DONE, pending_tool=None, pending_arguments=None)
            return
        exposure = exposure_of(approved)
        if turn.state.duplicate:
            reason = DisputeReason.DUPLICATE
        elif turn.state.claim_type is ClaimType.IMPROPER_CHARGE:
            reason = DisputeReason.BANK_CHARGE
        else:
            reason = DisputeReason.FRAUD
        args = RegisterDisputeInput(
            charges_n=[d.n for d in details],
            reason=reason,
            declared_channel=turn.state.declared_channel or DeclaredChannel.UNKNOWN,
            confirmation_token=PENDING_TOKEN,
        )
        confirmation = self._tools.confirm(turn.session, "register_dispute", args)
        args = args.model_copy(update={"confirmation_token": confirmation.token})
        shown = " + ".join(self._money(turn, m) for m in exposure)
        template = "confirm_register_one" if len(details) == 1 else "confirm_register"
        turn.lines.append(self._text(turn, template, charges=charges_text(turn, len(details)), exposure=shown))
        self._yes_no(turn)
        turn.pending = PendingConfirmation(
            action="register_dispute", summary=shown, expires_at=aware(confirmation.expires_at)
        )
        turn.state = turn.state.advance(
            step=Step.CONFIRM_REGISTER, pending_tool="register_dispute", pending_arguments=args.model_dump(mode="json")
        )

    def _on_register(self, turn: Turn, reading: Interpretation) -> None:
        if reading.answer is Answer.NO:
            # The customer's decision is acknowledged before the closing advice.
            turn.lines.append(self._text(turn, "register_skipped"))
            turn.lines.append(self._text(turn, "closing"))
            turn.state = turn.state.advance(step=Step.DONE, pending_tool=None, pending_arguments=None)
            return
        if reading.answer is not Answer.YES:
            self._ask_again(turn, "confirm_options", step=Step.CONFIRM_REGISTER)
            return
        args = RegisterDisputeInput.model_validate(turn.state.pending_arguments)
        claim = turn.state.claim_type or ClaimType.UNRECOGNIZED_CHARGE
        result = self._tools.register_dispute(turn.session, self._offers(turn), args, claim)
        self._record_write(turn, "register_dispute", args, result.output, result.read_back_matches)
        if isinstance(result.output, ToolError) and result.output.case_id:
            self._repeat_case(turn, result.output.case_id)
            return
        if not (result.read_back_matches and isinstance(result.output, RegisterDisputeOutput)):
            self._fail(turn)
            return
        case = self._tools.read_case(turn.session, ReadCaseInput(case_id=result.output.case_id))
        if isinstance(case, ToolError):
            self._fail(turn)
            return
        turn.lines.append(self._text(turn, "case_registered", case_id=result.output.case_id))
        turn.state = turn.state.advance(case_id=result.output.case_id, pending_tool=None, pending_arguments=None)
        legal = self._legal_lines(turn, case)
        self._close_case(turn, case, legal)

    def _repeat_case(self, turn: Turn, case_id: str) -> None:
        """A charge already in a case gets that case and its deadlines, never a second case."""
        turn.lines.append(self._text(turn, "repeat_case", case_id=case_id))
        case = self._tools.read_case(turn.session, ReadCaseInput(case_id=case_id))
        if isinstance(case, Case):
            self._legal_lines(turn, case)
        turn.lines.append(self._text(turn, "closing"))
        turn.state = turn.state.advance(step=Step.DONE, case_id=case_id, pending_tool=None, pending_arguments=None)

    def _legal_lines(self, turn: Turn, case: Case) -> LegalAssessment:
        """Deadlines of the case, counted from the day it was filed and with the channel it was filed with."""
        first = min(case.charges, key=lambda charge: charge.occurred_at)
        legal = assess(
            self._legal,
            self._country(turn),
            case.declared_channel,
            first.country,
            first.card_type,
            event_day=first.occurred_at.date(),
            filing_day=case.created_at.date(),
        )
        language = language_of(turn.state.variant)
        for due in legal.dues:
            if due.due is None or due.party.value != "bank":
                continue
            name = f"deadline_{due.rule_id}"
            if due.rule_id == "AR-R05":
                name = "deadline_AR-R05_ack" if "acknowledge" in due.what else "deadline_AR-R05_answer"
            turn.lines.append(self._text(turn, name, date=day(due.due, language)))
            rule = self._legal.rule(due.rule_id)
            turn.glass_box.append(
                GlassBoxEntry(
                    rule_id=due.rule_id, source=f"{rule.source.title}, {rule.source.provision}", deadline=due.due
                )
            )
        for step in legal.without_date:
            turn.lines.append(self._text(turn, "route_without_date", route=step.name[language.value]))
        return legal

    def _close_case(self, turn: Turn, case: Case, legal: LegalAssessment) -> None:
        customer = self._tools.customer(turn.session)
        signals = set(turn.state.signals)
        evaluation = self._evaluate(turn, self._dispute_facts(turn, [], case=case))
        escalate = evaluation.escalate or turn.state.escalated
        if escalate:
            queue = evaluation.queue or turn.state.queue or Queue.COMPLAINTS
            goodwill = Outcome.GOODWILL_CANDIDATE in evaluation.outcomes
            details = [d for d in (self._detail(turn, n) for n in turn.state.disputed) if d is not None]
            band = (
                FraudScoreBand.ABOVE_30
                if any(d.fraud_score_band is FraudScoreBand.ABOVE_30 for d in details)
                else (FraudScoreBand.AT_MOST_30)
            )
            handoff = build_handoff(
                case=case,
                customer=customer,
                variant=turn.state.variant,
                response_level=3 if "POL-06" in turn.state.rules_applied else 2,
                fraud_score_band=band,
                declared=DeclaredFacts(channel=turn.state.declared_channel, has_card=turn.state.has_card),
                sweep=Sweep(charges_reviewed=len(turn.state.charges_offered), not_recognized=len(turn.state.disputed)),
                actions=self._actions(turn),
                legal=legal,
                risk_signals=tuple(sorted(s.value for s in signals if s is not Signal.NEW_MERCHANT)),
                fraud_alert=Outcome.FRAUD_ALERT in evaluation.outcomes,
                goodwill=GoodwillCandidate(
                    flagged=goodwill,
                    criteria=tuple(GoodwillCriterion) if goodwill else (),
                    reason="policy section 11.1 criteria met" if goodwill else None,
                ),
                queue=queue,
                rules_applied=tuple(dict.fromkeys(turn.state.rules_applied)),
                open_questions=(CARD_LAST_SEEN,) if Signal.CARD_NOT_IN_POSSESSION in signals else (),
                policy_version=self._engine.version,
                created_at=aware(self._now()),
            )
            result = self._tools.create_handoff(
                turn.session, CreateHandoffInput(case_id=case.case_id, queue=queue), handoff
            )
            self._record(
                turn, EventType.HANDOFF, {"case_id": case.case_id, "queue": queue.value, "ok": result.read_back_matches}
            )
            turn.lines.append(self._text(turn, "handoff_pt" if turn.state.variant is LanguageVariant.PT else "handoff"))
            turn.state = turn.state.advance(escalated=True, queue=queue)
        if Outcome.FRAUD_ALERT in evaluation.outcomes and not turn.state.fraud_alert_charges:
            turn.state = turn.state.advance(fraud_alert_charges=[charge.n for charge in case.charges])
        turn.lines.append(self._text(turn, "closing"))
        turn.state = turn.state.advance(step=Step.HANDED_OFF if escalate else Step.DONE)
