from fastapi import APIRouter, Depends

from api.context import AppContext, get_context
from api.guards import analyst_session
from api.routers import API_PREFIX
from api.schemas import HealthResponse, MetricsResponse
from api.security import SessionToken

router = APIRouter(prefix=API_PREFIX, tags=["operations"])


@router.get("/health", response_model=HealthResponse)
def health(context: AppContext = Depends(get_context)) -> HealthResponse:
    container = context.container
    status = "degraded" if container.degraded else "ok"
    return HealthResponse(status=status, llm_provider=container.interpreter, version=context.settings.version)


@router.get("/metrics", response_model=MetricsResponse)
def operations_metrics(
    _: SessionToken = Depends(analyst_session), context: AppContext = Depends(get_context)
) -> MetricsResponse:
    container = context.container
    llm = container.llm_usage() if container.llm_usage else None
    return MetricsResponse(
        interpreter=container.interpreter, degraded=container.degraded, llm=llm, **context.metrics.snapshot()
    )
