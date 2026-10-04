"""Implementation of the tools port: read tools straight from the toolbox, writes only through the action gate.

An adapter that fails (a database that does not answer, a timeout) reaches the flow as a typed tool error, never as
a crash, so the flow can hand the case to a person without filling anything in (POL-13). Reads are tried twice;
writes are not, because the gate spends the confirmation token on the first attempt.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from pydantic import BaseModel

from vera.contracts.cases import Case
from vera.contracts.charges import ChargeDetail
from vera.contracts.handoff import Handoff, Transfer
from vera.contracts.interpretation import ClaimType
from vera.contracts.tools import (
    BlockCardInput,
    CreateHandoffInput,
    CreateTransferInput,
    ReadCaseInput,
    RegisterDisputeInput,
    SearchChargesInput,
    SearchChargesOutput,
    SendFraudAlertInput,
    SweepChargesInput,
    SweepChargesOutput,
    ToolError,
    ToolErrorCode,
    ViewChargeInput,
)
from vera.ports.bank import CustomerRecord, CustomersPort, TransactionsPort
from vera.ports.tools import Confirmation, GateResult, Offers, Session
from vera.tools.gate import ActionGate
from vera.tools.toolbox import Toolbox

logger = logging.getLogger("vera.tools")
READ_ATTEMPTS = 2


def guarded[T](tool: str, call: Callable[[], T], attempts: int = 1) -> T | ToolError:
    """The result of the call, or a failure error once every attempt raised."""
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except Exception:  # any adapter failure is a tool failure for the flow (POL-13)
            logger.warning("tool %s failed, attempt %d of %d", tool, attempt, attempts, exc_info=True)
    return ToolError(code=ToolErrorCode.FAILURE)


def guarded_write(tool: str, call: Callable[[], GateResult]) -> GateResult:
    result = guarded(tool, call)
    return GateResult(result, read_back_matches=False) if isinstance(result, ToolError) else result


class ToolService:
    def __init__(
        self,
        toolbox: Toolbox,
        gate: ActionGate,
        customers: CustomersPort,
        transactions: TransactionsPort,
        now: Callable[[], datetime],
    ) -> None:
        self._toolbox = toolbox
        self._gate = gate
        self._customers = customers
        self._transactions = transactions
        self._now = now

    def customer(self, session: Session) -> CustomerRecord | None:
        return self._customers.customer(session.customer_ref)

    def disputes_in_last_days(self, session: Session, days: int) -> int:
        return self._transactions.disputes_since(session.customer_ref, self._now() - timedelta(days=days))

    def search_charges(
        self, session: Session, offers: Offers, args: SearchChargesInput
    ) -> tuple[SearchChargesOutput, Offers] | ToolError:
        return guarded("search_charges", lambda: self._toolbox.search_charges(session, offers, args), READ_ATTEMPTS)

    def view_charge(self, session: Session, offers: Offers, args: ViewChargeInput) -> ChargeDetail | ToolError:
        return guarded("view_charge", lambda: self._toolbox.view_charge(session, offers, args), READ_ATTEMPTS)

    def sweep_charges(
        self, session: Session, offers: Offers, args: SweepChargesInput
    ) -> tuple[SweepChargesOutput, Offers] | ToolError:
        return guarded("sweep_charges", lambda: self._toolbox.sweep_charges(session, offers, args), READ_ATTEMPTS)

    def read_case(self, session: Session, args: ReadCaseInput) -> Case | ToolError:
        return guarded("read_case", lambda: self._toolbox.read_case(session, args), READ_ATTEMPTS)

    def confirm(self, session: Session, tool: str, arguments: BaseModel) -> Confirmation:
        return self._gate.confirm(session, tool, arguments)

    def block_card(self, session: Session, offers: Offers, args: BlockCardInput) -> GateResult:
        return guarded_write("block_card", lambda: self._gate.block_card(session, offers, args))

    def register_dispute(
        self, session: Session, offers: Offers, args: RegisterDisputeInput, claim_type: ClaimType
    ) -> GateResult:
        return guarded_write("register_dispute", lambda: self._gate.register_dispute(session, offers, args, claim_type))

    def create_handoff(self, session: Session, args: CreateHandoffInput, handoff: Handoff) -> GateResult:
        return guarded_write("create_handoff", lambda: self._gate.create_handoff(session, args, handoff))

    def create_transfer(self, session: Session, args: CreateTransferInput, note: Transfer) -> GateResult:
        return guarded_write("create_transfer", lambda: self._gate.create_transfer(session, args, note))

    def send_fraud_alert(self, session: Session, offers: Offers, args: SendFraudAlertInput) -> GateResult:
        return guarded_write("send_fraud_alert", lambda: self._gate.send_fraud_alert(session, offers, args))
