"""The analyst's desk: the queue of what waits for a person, and each case handoff or transfer note."""

from api.failures import ApiFailure
from api.schemas import ApiErrorCode, QueueItem
from vera.contracts.handoff import Handoff, Transfer
from vera.ports.bank import AnalystQueuePort


class AnalystDesk:
    def __init__(self, state: AnalystQueuePort) -> None:
        self._state = state

    def queue(self) -> list[QueueItem]:
        """What waits for an analyst, newest first: case handoffs and transfer notes."""
        return [queue_item(item) for item in self._state.queue()]

    def handoff(self, case_id: str) -> Handoff:
        found = self._state.handoff_of(case_id)
        if found is None:
            raise ApiFailure(ApiErrorCode.NOT_FOUND)
        return found

    def transfer(self, transfer_id: str) -> Transfer:
        found = self._state.transfer_of(transfer_id)
        if found is None:
            raise ApiFailure(ApiErrorCode.NOT_FOUND)
        return found


def queue_item(item: Handoff | Transfer) -> QueueItem:
    """The line of the queue for a handoff or a transfer, with the parts of its summary as codes."""
    transfer = isinstance(item, Transfer)
    return QueueItem(
        kind="transfer" if transfer else "case",
        reference=item.transfer_id if transfer else item.case_id,
        created_at=item.created_at,
        queue=item.suggested_queue,
        summary=item.summary,
        requires_pt_analyst=item.requires_pt_analyst,
        trace_id=item.trace_id,
        claim_type=item.claim_type,
        reason=item.reason,
        charge_count=len(item.charges) if transfer else len(item.verified_facts.charges),
        pending_action=item.pending_action_not_run if transfer else None,
    )
