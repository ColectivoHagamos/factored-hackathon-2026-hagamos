"""HTTP entry point. Routes only authenticate, validate and delegate; business rules live in the domain."""

import hmac
import logging
import re
import secrets
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from api.dependencies import Container, build
from api.observability import Metrics, configure_logging, log_event, turn_summary
from api.security import SESSION_TTL, InvalidSessionError, SessionToken
from api.settings import Settings
from vera.contracts.api import (
    ApiError,
    ApiErrorCode,
    CaseView,
    DemoSessionRequest,
    DemoSessionResponse,
    HealthResponse,
    MessageRequest,
    MessageResponse,
    MetricsResponse,
    QueueItem,
    StartConversationRequest,
    StartConversationResponse,
)
from vera.contracts.cases import Case
from vera.contracts.handoff import Handoff, Transfer
from vera.contracts.tools import ReadCaseInput
from vera.gateway.injection import signals as injection_signals
from vera.gateway.masking import mask
from vera.ports.tools import Session

PREFIX = "/v1"
WEB = Path(__file__).resolve().parents[1] / "web"
STATUS = {
    ApiErrorCode.UNAUTHORIZED: 401,
    ApiErrorCode.NOT_FOUND: 404,
    ApiErrorCode.CONFIRMATION_EXPIRED: 409,
    ApiErrorCode.RATE_LIMITED: 429,
    ApiErrorCode.PROVIDER_UNAVAILABLE: 503,
}
MESSAGES = {
    ApiErrorCode.UNAUTHORIZED: "Session missing, invalid or expired",
    ApiErrorCode.NOT_FOUND: "Not found",
    ApiErrorCode.RATE_LIMITED: "Too many messages; wait a minute",
    ApiErrorCode.PROVIDER_UNAVAILABLE: "Service temporarily unavailable; try again in a moment",
}
logger = logging.getLogger("vera.api")


class DemoCustomer(BaseModel):
    customer_ref: str
    alias: str
    country: str
    segment: str
    scenarios: list[str]


class ApiFailure(Exception):
    def __init__(self, code: ApiErrorCode) -> None:
        self.code = code


class RateLimiter:
    def __init__(self, per_minute: int, now: Callable[[], datetime]) -> None:
        self._per_minute = per_minute
        self._now = now
        self._calls: defaultdict[str, deque[datetime]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = self._now()
        calls = self._calls[key]
        while calls and now - calls[0] > timedelta(minutes=1):
            calls.popleft()
        if len(calls) >= self._per_minute:
            raise ApiFailure(ApiErrorCode.RATE_LIMITED)
        calls.append(now)


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    """Build the application for the given settings, or for the environment when none are given."""
    settings = settings or Settings.from_env()
    container = container or build(settings)
    limiter = RateLimiter(settings.messages_per_minute, container.now)
    metrics = Metrics()
    app = FastAPI(
        title="VERA API",
        version=settings.version,
        docs_url=f"{PREFIX}/docs",
        openapi_url=f"{PREFIX}/openapi.json",
        redoc_url=None,
    )

    @app.middleware("http")
    async def operations(request: Request, call_next):
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
            metrics.request(status, ms)
            log_event("request", request_id=request_id, method=request.method, route=route, status=status, ms=ms)

    @app.exception_handler(ApiFailure)
    def failure(_: Request, error: ApiFailure) -> JSONResponse:
        body = ApiError(code=error.code, message=MESSAGES.get(error.code, error.code.value.replace("_", " ")))
        return JSONResponse(body.model_dump(mode="json"), status_code=STATUS[error.code])

    @app.exception_handler(Exception)
    def unexpected(_: Request, error: Exception) -> JSONResponse:
        # Nothing internal reaches the client; the operators get the trace in the log.
        logger.error("unexpected error", exc_info=error)
        return failure(_, ApiFailure(ApiErrorCode.PROVIDER_UNAVAILABLE))

    def customer_session(authorization: str = Header(default="")) -> SessionToken:
        return _verify(container, authorization, "customer")

    def analyst_session(authorization: str = Header(default="")) -> SessionToken:
        return _verify(container, authorization, "analyst")

    @app.get(f"{PREFIX}/health", response_model=HealthResponse, tags=["operations"])
    def health() -> HealthResponse:
        status = "degraded" if container.degraded else "ok"
        return HealthResponse(status=status, llm_provider=container.interpreter, version=settings.version)

    @app.get(f"{PREFIX}/metrics", response_model=MetricsResponse, tags=["operations"])
    def operations_metrics(session: SessionToken = Depends(analyst_session)) -> MetricsResponse:
        llm = container.llm_usage() if container.llm_usage else None
        return MetricsResponse(
            interpreter=container.interpreter, degraded=container.degraded, llm=llm, **metrics.snapshot()
        )

    @app.get(f"{PREFIX}/demo-customers", response_model=list[DemoCustomer], tags=["demo"])
    def demo_customers() -> list[DemoCustomer]:
        return [
            DemoCustomer(
                customer_ref=c.customer_ref,
                alias=c.alias,
                country=c.country.value,
                segment=c.segment,
                scenarios=list(c.scenarios),
            )
            for c in container.customers.customers()
        ]

    @app.post(f"{PREFIX}/demo-session", response_model=DemoSessionResponse, tags=["demo"])
    def demo_session(body: DemoSessionRequest) -> DemoSessionResponse:
        if container.customers.customer(body.demo_customer) is None:
            raise ApiFailure(ApiErrorCode.NOT_FOUND)
        token = container.signer.issue(body.demo_customer)
        return DemoSessionResponse(token=token, expires_at=(container.now() + SESSION_TTL).astimezone())

    @app.post(f"{PREFIX}/demo-analyst-session", response_model=DemoSessionResponse, tags=["demo"])
    def demo_analyst_session(x_analyst_key: str = Header(default="")) -> DemoSessionResponse:
        if settings.analyst_key and not hmac.compare_digest(x_analyst_key, settings.analyst_key):
            raise ApiFailure(ApiErrorCode.UNAUTHORIZED)
        token = container.signer.issue("demo-analyst", role="analyst")
        return DemoSessionResponse(token=token, expires_at=(container.now() + SESSION_TTL).astimezone())

    @app.post(f"{PREFIX}/conversations", response_model=StartConversationResponse, tags=["conversation"])
    def start(
        body: StartConversationRequest, session: SessionToken = Depends(customer_session)
    ) -> StartConversationResponse:
        conversation_id = secrets.token_hex(8)
        container.state.open_conversation(conversation_id, session.subject)
        opening = container.conversation.start(Session(session.subject, conversation_id), body.preferred_language)
        metrics.conversation()
        return StartConversationResponse(
            conversation_id=conversation_id, greeting=opening.reply, options=opening.options
        )

    @app.post(
        f"{PREFIX}/conversations/{{conversation_id}}/messages", response_model=MessageResponse, tags=["conversation"]
    )
    def message(
        conversation_id: str, body: MessageRequest, request: Request, session: SessionToken = Depends(customer_session)
    ) -> MessageResponse:
        _own(container, conversation_id, session)
        limiter.check(session.subject)
        # Injection signals are read on the original text; only the masked text goes further.
        signals = injection_signals(body.text) if body.text else ()
        masked = body.model_copy(update={"text": mask(body.text)}) if body.text else body
        started = time.perf_counter()
        reply = container.conversation.reply(Session(session.subject, conversation_id), masked, signals)
        ms = round((time.perf_counter() - started) * 1000, 1)
        # The conversation id is the trace id: these lines and the hash-chained event log tell the same turn.
        summary = turn_summary(container.conversation.history(conversation_id))
        metrics.turn(summary, ms)
        log_event("turn", trace_id=f"trace-{conversation_id}", request_id=request.state.request_id, ms=ms, **summary)
        return reply

    @app.get(f"{PREFIX}/cases/{{case_id}}", response_model=CaseView, tags=["cases"])
    def case(case_id: str, session: SessionToken = Depends(customer_session)) -> CaseView:
        try:
            query = ReadCaseInput(case_id=case_id)
        except ValidationError as error:
            raise ApiFailure(ApiErrorCode.NOT_FOUND) from error
        found = container.tools.read_case(Session(session.subject, ""), query)
        if not isinstance(found, Case):
            raise ApiFailure(ApiErrorCode.NOT_FOUND)
        handoff = container.state.handoff_of(case_id)
        deadline = next((o.due for o in handoff.legal_clock.obligations if o.due), None) if handoff else None
        return CaseView(case=found, legal_route=handoff.legal_clock.route if handoff else None, deadline=deadline)

    @app.get(f"{PREFIX}/cases/{{case_id}}/handoff", response_model=Handoff, tags=["cases"])
    def handoff(case_id: str, _: SessionToken = Depends(analyst_session)) -> Handoff:
        found = container.state.handoff_of(case_id)
        if found is None:
            raise ApiFailure(ApiErrorCode.NOT_FOUND)
        return found

    @app.get(f"{PREFIX}/transfers/{{transfer_id}}", response_model=Transfer, tags=["cases"])
    def transfer(transfer_id: str, _: SessionToken = Depends(analyst_session)) -> Transfer:
        found = container.state.transfer_of(transfer_id)
        if found is None:
            raise ApiFailure(ApiErrorCode.NOT_FOUND)
        return found

    @app.get(f"{PREFIX}/queue", response_model=list[QueueItem], tags=["cases"])
    def queue(_: SessionToken = Depends(analyst_session)) -> list[QueueItem]:
        """What waits for an analyst, newest first: case handoffs and transfer notes."""
        return [QueueItem.of(item) for item in container.state.queue()]

    # ADR 0002: the API also serves the web, so the demo is one URL and one deployment.
    if WEB.is_dir():
        app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
    return app


def _request_id(header: str | None) -> str:
    """The caller's request id when it is a plain token, so a trace can cross services; otherwise a new one."""
    return header if header and re.fullmatch(r"[A-Za-z0-9-]{8,64}", header) else uuid.uuid4().hex


def _verify(container: Container, authorization: str, role: str) -> SessionToken:
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return container.signer.verify(token, role)
    except InvalidSessionError as error:
        raise ApiFailure(ApiErrorCode.UNAUTHORIZED) from error


def _own(container: Container, conversation_id: str, session: SessionToken) -> None:
    """A conversation of another customer answers exactly like one that does not exist."""
    if container.state.conversation_owner(conversation_id) != session.subject:
        raise ApiFailure(ApiErrorCode.NOT_FOUND)


configure_logging()
app = create_app()
