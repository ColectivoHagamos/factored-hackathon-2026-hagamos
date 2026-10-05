from fastapi import APIRouter, Depends

from api.context import AppContext, get_context
from api.guards import access_session
from api.routers import API_PREFIX
from api.schemas import DataOverview
from api.security import SessionToken

router = APIRouter(prefix=API_PREFIX, tags=["data"])


@router.get("/data/overview", response_model=DataOverview)
def data_overview(
    _: SessionToken | None = Depends(access_session), context: AppContext = Depends(get_context)
) -> DataOverview:
    """Totals of the data behind the demo, behind the same login as the demo customers."""
    return context.data.overview()
