from fastapi import APIRouter, Depends, Header

from api.context import AppContext, get_context
from api.guards import access_session
from api.routers import API_PREFIX
from api.schemas import DemoCustomer, DemoSessionRequest, DemoSessionResponse
from api.security import SessionToken

router = APIRouter(prefix=API_PREFIX, tags=["demo"])


@router.get("/demo-customers", response_model=list[DemoCustomer])
def demo_customers(
    _: SessionToken | None = Depends(access_session), context: AppContext = Depends(get_context)
) -> list[DemoCustomer]:
    return context.demo.customers()


@router.post("/demo-session", response_model=DemoSessionResponse)
def demo_session(
    body: DemoSessionRequest,
    _: SessionToken | None = Depends(access_session),
    context: AppContext = Depends(get_context),
) -> DemoSessionResponse:
    return context.demo.customer_session(body.demo_customer)


@router.post("/demo-analyst-session", response_model=DemoSessionResponse)
def demo_analyst_session(
    x_analyst_key: str = Header(default=""),
    _: SessionToken | None = Depends(access_session),
    context: AppContext = Depends(get_context),
) -> DemoSessionResponse:
    return context.demo.analyst_session(x_analyst_key)
