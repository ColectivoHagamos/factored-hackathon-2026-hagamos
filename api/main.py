"""The process entry point: uvicorn serves api.main:app (docker/api.Dockerfile); the application is built by
api.app.create_app, which tests call with their own settings and container."""

from api.app import create_app
from api.observability import configure_logging

__all__ = ["app", "create_app"]

configure_logging()
app = create_app()
