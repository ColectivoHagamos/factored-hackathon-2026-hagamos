"""Implementation of the tools port: read tools straight from the toolbox, writes only through the action gate."""

from collections.abc import Callable
from datetime import datetime, timedelta

from pydantic import BaseModel

from vera.contracts.cases import Case
from vera.contracts.charges import ChargeDetail
from vera.contracts.handoff import Handoff
from vera.contracts.interpretation import ClaimType
from vera.contracts.tools import (
    BlockCardInput,
    CreateHandoffInput,
    ReadCaseInput,
    RegisterDisputeInput,
    SearchChargesInput,
    SearchChargesOutput,
    SendFraudAlertInput,
    SweepChargesInput,
    SweepChargesOutput,
    ToolError,
    ViewChargeInput,
)
from vera.ports.bank import CustomerRecord, CustomersPort, TransactionsPort
from vera.ports.tools import Confirmation, GateResult, Offers, Session
from vera.tools.gate import ActionGate
from vera.tools.toolbox import Toolbox


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
        return self._toolbox.search_charges(session, offers, args)

    def view_charge(self, session: Session, offers: Offers, args: ViewChargeInput) -> ChargeDetail | ToolError:
        return self._toolbox.view_charge(session, offers, args)

    def sweep_charges(
        self, session: Session, offers: Offers, args: SweepChargesInput
    ) -> tuple[SweepChargesOutput, Offers] | ToolError:
        return self._toolbox.sweep_charges(session, offers, args)

    def read_case(self, session: Session, args: ReadCaseInput) -> Case | ToolError:
        return self._toolbox.read_case(session, args)

    def confirm(self, session: Session, tool: str, arguments: BaseModel) -> Confirmation:
        return self._gate.confirm(session, tool, arguments)

    def block_card(self, session: Session, offers: Offers, args: BlockCardInput) -> GateResult:
        return self._gate.block_card(session, offers, args)

    def register_dispute(
        self, session: Session, offers: Offers, args: RegisterDisputeInput, claim_type: ClaimType
    ) -> GateResult:
        return self._gate.register_dispute(session, offers, args, claim_type)

    def create_handoff(self, session: Session, args: CreateHandoffInput, handoff: Handoff) -> GateResult:
        return self._gate.create_handoff(session, args, handoff)

    def send_fraud_alert(self, session: Session, offers: Offers, args: SendFraudAlertInput) -> GateResult:
        return self._gate.send_fraud_alert(session, offers, args)
