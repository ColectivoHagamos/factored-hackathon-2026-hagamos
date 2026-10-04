"""HTTP entry point. Routes only validate and delegate; business rules live in the domain."""

from fastapi import FastAPI

from api.settings import Settings
from vera.contracts.api import HealthResponse

PREFIX = "/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application for the given settings, or for the environment when none are given."""
    settings = settings or Settings.from_env()
    app = FastAPI(
        title="VERA API",
        version=settings.version,
        docs_url=f"{PREFIX}/docs",
        openapi_url=f"{PREFIX}/openapi.json",
        redoc_url=None,
    )

    @app.get(f"{PREFIX}/health", response_model=HealthResponse, tags=["operations"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", llm_provider=settings.llm, version=settings.version)

    return app


app = create_app()
