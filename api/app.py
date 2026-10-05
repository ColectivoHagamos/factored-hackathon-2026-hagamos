"""The application factory: the context, the operations middleware, the error answers, the routers and the web."""

import logging
import re
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.context import build_context
from api.dependencies import Container, build
from api.failures import ApiFailure
from api.observability import log_event
from api.routers import API_PREFIX, access, analyst, conversations, customer, data, demo, operations, pages
from api.schemas import ApiError, ApiErrorCode
from api.settings import Settings
from api.web import SinglePageApp

# The built web (npm run build in web/); the image copies it here (ADR 0006).
WEB = Path(__file__).resolve().parents[1] / "web" / "dist"
# In this order, so the OpenAPI document lists the paths as the product reads them.
ROUTERS = (access, operations, demo, data, conversations, customer, analyst, pages)
logger = logging.getLogger("vera.api")


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    """Build the application for the given settings, or for the environment when none are given."""
    settings = settings or Settings.from_env()
    app = FastAPI(
        title="VERA API",
        version=settings.version,
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
        redoc_url=None,
    )
    app.state.context = build_context(settings, container or build(settings))
    app.middleware("http")(_operations)
    app.add_exception_handler(ApiFailure, _failure)
    app.add_exception_handler(Exception, _unexpected)
    for module in ROUTERS:
        app.include_router(module.router)
    # ADR 0006: the API serves the built web, so the product is one URL and one deployment.
    web = Path(settings.web_dir) if settings.web_dir else WEB
    if web.is_dir():
        app.mount("/", SinglePageApp(directory=web, html=True), name="web")
    return app


async def _operations(request: Request, call_next):
    """One JSON line per request, with its id echoed back; the route template, never the ids in the path."""
    request_id = _request_id(request.headers.get("x-request-id"))
    request.state.request_id = request_id
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        ms = round((time.perf_counter() - started) * 1000, 1)
        route = getattr(request.scope.get("route"), "path", None) or "static"
        request.app.state.context.metrics.request(status, ms)
        log_event("request", request_id=request_id, method=request.method, route=route, status=status, ms=ms)


def _failure(_: Request, error: ApiFailure) -> JSONResponse:
    body = ApiError(code=error.code, message=error.message)
    return JSONResponse(body.model_dump(mode="json"), status_code=error.status)


def _unexpected(request: Request, error: Exception) -> JSONResponse:
    # Nothing internal reaches the client; the operators get the trace in the log.
    logger.error("unexpected error", exc_info=error)
    return _failure(request, ApiFailure(ApiErrorCode.PROVIDER_UNAVAILABLE))


def _request_id(header: str | None) -> str:
    """The caller's request id when it is a plain token, so a trace can cross services; otherwise a new one."""
    return header if header and re.fullmatch(r"[A-Za-z0-9-]{8,64}", header) else uuid.uuid4().hex
