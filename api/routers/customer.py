from fastapi import APIRouter, Depends

from api.context import AppContext, get_context
from api.guards import customer_session
from api.routers import API_PREFIX
from api.schemas import CaseView, MeResponse, Movement
from api.security import SessionToken

router = APIRouter(prefix=API_PREFIX)


@router.get("/me", response_model=MeResponse, tags=["customer"])
def me(session: SessionToken = Depends(customer_session), context: AppContext = Depends(get_context)) -> MeResponse:
    return context.customers.profile(session.subject)


@router.get("/me/movements", response_model=list[Movement], tags=["customer"])
def movements(
    session: SessionToken = Depends(customer_session), context: AppContext = Depends(get_context)
) -> list[Movement]:
    """The session customer's movements, newest first: what the bank's app would show before a dispute."""
    return context.customers.movements(session.subject)


@router.get("/cases/{case_id}", response_model=CaseView, tags=["cases"])
def case(
    case_id: str, session: SessionToken = Depends(customer_session), context: AppContext = Depends(get_context)
) -> CaseView:
    return context.customers.case(session.subject, case_id)
