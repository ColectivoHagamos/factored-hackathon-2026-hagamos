"""A person takes over: the transfer note, the failure of a tool (POL-13) and the fraud alert when one is due
(POL-16)."""

from vera.contracts.events import EventType
from vera.contracts.handoff import DeclaredFacts, Queue, Transfer, TransferReason
from vera.contracts.tools import CreateTransferInput, SendFraudAlertInput, ToolError
from vera.core.state import Step
from vera.core.steps.base import INVALID_NOTE, FlowSupport, Turn, aware
from vera.output.handoff import build_transfer
from vera.policy.engine import Facts, Signal


class HandoffSteps(FlowSupport):
    """Handing the conversation to a person, and the alerts that go with it."""

    def _alert_fraud_if_due(self, turn: Turn) -> None:
        """POL-16: when the dispute part ends, with or without a case, the Fraud team gets one alert."""
        state = turn.state
        if not state.fraud_alert_charges or state.fraud_alert_id or state.step not in (Step.DONE, Step.HANDED_OFF):
            return
        args = SendFraudAlertInput(
            charges_n=tuple(state.fraud_alert_charges),
            signals=tuple(signal.value for signal in state.signals),
            card_blocked=any(a.action == "block_card" and a.result == "ok" for a in self._actions(turn)),
            case_id=state.case_id,
        )
        result = self._tools.send_fraud_alert(turn.session, self._offers(turn), args)
        self._record_tool(turn, "send_fraud_alert", args.model_dump(mode="json"), result.output)
        if isinstance(result.output, ToolError):
            # POL-13: a person follows up; the next turn tries the alert again.
            if state.step is not Step.HANDED_OFF:
                self._fail(turn)
            return
        alert_id = result.output.alert_id
        self._record(turn, EventType.FRAUD_ALERT, {"alert_id": alert_id, **args.model_dump(mode="json")})
        turn.state = turn.state.advance(fraud_alert_id=alert_id)

    def _fail(self, turn: Turn) -> None:
        """POL-13: a failed tool or a read-back that does not match goes to a person; nothing is filled in."""
        self._evaluate(
            turn, Facts(account_country=self._country(turn), tool_failed=True, already_escalated=turn.state.escalated)
        )
        turn.lines.append(self._text(turn, "tool_failure"))
        self._hand_off(turn, Queue.COMPLAINTS, TransferReason.TOOL_FAILURE)

    def _hand_off(self, turn: Turn, queue: Queue, reason: TransferReason) -> None:
        """A person takes over, and the analyst gets a note with what is already known (POL-01)."""
        transfer_id = self._leave_note(turn, queue, reason)
        data = {"case_id": turn.state.case_id, "queue": queue.value, "transfer_id": transfer_id}
        self._record(turn, EventType.HANDOFF, data)
        turn.state = turn.state.advance(step=Step.HANDED_OFF, escalated=True, queue=queue)

    def _leave_note(self, turn: Turn, queue: Queue, reason: TransferReason) -> str | None:
        """The transfer note; when it cannot be built or kept, the conversation still goes to the person."""
        args = CreateTransferInput(queue=queue, reason=reason)
        try:
            note = self._transfer_note(turn, queue, reason)
        except ValueError:
            self._record_tool(turn, "create_transfer", args.model_dump(mode="json"), INVALID_NOTE)
            return None
        result = self._tools.create_transfer(turn.session, args, note)
        self._record_tool(turn, "create_transfer", args.model_dump(mode="json"), result.output)
        return None if isinstance(result.output, ToolError) else result.output.transfer_id

    def _transfer_note(self, turn: Turn, queue: Queue, reason: TransferReason) -> Transfer:
        state = turn.state
        known = state.disputed or ([state.chosen] if state.chosen is not None else sorted(state.charges_offered))
        signals = tuple(sorted(s.value for s in state.signals if s is not Signal.NEW_MERCHANT))
        return build_transfer(
            reason=reason,
            customer=self._tools.customer(turn.session),
            variant=state.variant,
            claim_type=state.claim_type,
            charges=tuple(d for d in (self._detail(turn, n) for n in known) if d is not None),
            declared=DeclaredFacts(
                channel=state.declared_channel,
                has_card=state.has_card,
                authorized_payment=state.authorized_payment,
                date_text=state.date_text,
                contacted_by=state.contacted_by,
            ),
            actions=self._actions(turn),
            pending_action=state.pending_tool,
            case_id=state.case_id,
            risk_signals=signals,
            fraud_alert=bool(state.fraud_alert_charges),
            rules_applied=tuple(dict.fromkeys(state.rules_applied)),
            queue=queue,
            policy_version=self._engine.version,
            conversation_id=turn.session.conversation_id,
            created_at=aware(self._now()),
        )
