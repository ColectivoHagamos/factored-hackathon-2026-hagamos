from fastapi import APIRouter, Depends

from api.context import AppContext, get_context
from api.guards import analyst_session
from api.routers import API_PREFIX
from api.schemas import QueueItem
from api.security import SessionToken
from vera.contracts.handoff import Handoff, Transfer

router = APIRouter(prefix=API_PREFIX, tags=["cases"])


@router.get("/cases/{case_id}/handoff", response_model=Handoff)
def handoff(
    case_id: str, _: SessionToken = Depends(analyst_session), context: AppContext = Depends(get_context)
) -> Handoff:
    return context.analyst.handoff(case_id)


@router.get("/transfers/{transfer_id}", response_model=Transfer)
def transfer(
    transfer_id: str, _: SessionToken = Depends(analyst_session), context: AppContext = Depends(get_context)
) -> Transfer:
    return context.analyst.transfer(transfer_id)


@router.get("/queue", response_model=list[QueueItem])
def queue(_: SessionToken = Depends(analyst_session), context: AppContext = Depends(get_context)) -> list[QueueItem]:
    """What waits for an analyst, newest first: case handoffs and transfer notes."""
    return context.analyst.queue()
