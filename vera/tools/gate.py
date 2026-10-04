"""Action gate: the only way a write reaches the bank.

Order of checks: risk table, then the confirmation token issued by the server (bound to the conversation, the
tool and the exact arguments, single use, with expiry), then the write with the token as idempotency key, and
finally the read-back. The agent reports "done" only when the read-back matches.
"""

import hashlib
import hmac
import json
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel

from vera.contracts.cases import Case
from vera.contracts.handoff import Handoff
from vera.contracts.interpretation import ClaimType
from vera.contracts.tools import (
    BlockCardInput,
    CreateHandoffInput,
    ReadCaseInput,
    RegisterDisputeInput,
    RegisterDisputeOutput,
    SendFraudAlertInput,
    ToolError,
    ToolErrorCode,
)
from vera.ports.tools import Confirmation, GateResult, Offers, Session
from vera.tools.toolbox import Toolbox


class Risk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"


# Reading is low risk; writes need confirmation. Moving or promising money has no tool at all (PROH-03).
RISK_TABLE: dict[str, Risk] = {
    "search_charges": Risk.LOW,
    "view_charge": Risk.LOW,
    "sweep_charges": Risk.LOW,
    "read_case": Risk.LOW,
    "block_card": Risk.MEDIUM,
    "register_dispute": Risk.MEDIUM,
    "create_handoff": Risk.MEDIUM,
    # An internal notice required by POL-16: it acts on nothing of the customer's, so it needs no confirmation.
    "send_fraud_alert": Risk.MEDIUM,
}
CONFIRMED_WRITES = ("block_card", "register_dispute")


def arguments_digest(arguments: BaseModel) -> str:
    """Canonical digest of the arguments of a write, without the token itself."""
    payload = arguments.model_dump(mode="json", exclude={"confirmation_token"})
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ActionGate:
    def __init__(
        self, toolbox: Toolbox, secret: bytes, now: Callable[[], datetime], ttl: timedelta = timedelta(minutes=10)
    ) -> None:
        self._toolbox = toolbox
        self._secret = secret
        self._now = now
        self._ttl = ttl
        self._used: set[str] = set()

    def confirm(self, session: Session, tool: str, arguments: BaseModel) -> Confirmation:
        """Issue the token the customer's confirmation unlocks; it is valid only for these exact arguments."""
        if RISK_TABLE.get(tool) is not Risk.MEDIUM or tool not in CONFIRMED_WRITES:
            raise ValueError(f"{tool} does not take a confirmation")
        expires_at = self._now() + self._ttl
        expiry = int(expires_at.timestamp())
        return Confirmation(f"tok_{expiry}_{self._signature(session, tool, arguments, expiry)}", tool, expires_at)

    def block_card(self, session: Session, offers: Offers, args: BlockCardInput) -> GateResult:
        refused = self._check(session, "block_card", args)
        if refused:
            return GateResult(refused, read_back_matches=False)
        output = self._toolbox.block_card(session, offers, args)
        if isinstance(output, ToolError):
            return GateResult(output, read_back_matches=False)
        return GateResult(output, self._toolbox.card_status(session, offers, args.card_n) == "blocked")

    def register_dispute(
        self, session: Session, offers: Offers, args: RegisterDisputeInput, claim_type: ClaimType
    ) -> GateResult:
        refused = self._check(session, "register_dispute", args)
        if refused:
            return GateResult(refused, read_back_matches=False)
        output = self._toolbox.register_dispute(session, offers, args, claim_type)
        if not isinstance(output, RegisterDisputeOutput):
            return GateResult(output, read_back_matches=False)
        stored = self._toolbox.read_case(session, ReadCaseInput(case_id=output.case_id))
        matches = isinstance(stored, Case) and stored.total_exposure == output.total_exposure
        return GateResult(output, read_back_matches=matches)

    def create_handoff(self, session: Session, args: CreateHandoffInput, handoff: Handoff) -> GateResult:
        output = self._toolbox.create_handoff(session, args, handoff)
        return GateResult(output, read_back_matches=not isinstance(output, ToolError))

    def send_fraud_alert(self, session: Session, offers: Offers, args: SendFraudAlertInput) -> GateResult:
        output = self._toolbox.send_fraud_alert(session, offers, args)
        return GateResult(output, read_back_matches=not isinstance(output, ToolError))

    def _check(self, session: Session, tool: str, args: BlockCardInput | RegisterDisputeInput) -> ToolError | None:
        token = args.confirmation_token
        try:
            prefix, expiry_text, signature = token.split("_", 2)
            expiry = int(expiry_text)
        except ValueError:
            return ToolError(code=ToolErrorCode.INVALID_TOKEN)
        expected = self._signature(session, tool, args, expiry)
        if prefix != "tok" or not hmac.compare_digest(signature, expected):
            return ToolError(code=ToolErrorCode.INVALID_TOKEN)
        if self._now().timestamp() > expiry or token in self._used:
            return ToolError(code=ToolErrorCode.INVALID_TOKEN)
        self._used.add(token)
        return None

    def _signature(self, session: Session, tool: str, arguments: BaseModel, expiry: int) -> str:
        message = f"{session.conversation_id}|{session.customer_ref}|{tool}|{arguments_digest(arguments)}|{expiry}"
        return hmac.new(self._secret, message.encode(), hashlib.sha256).hexdigest()[:40]
