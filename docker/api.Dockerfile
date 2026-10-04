# syntax=docker/dockerfile:1
# API image: locked dependencies, application code only, non-root user. No data or secrets inside.

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project

FROM python:3.12-slim AS runtime
ARG VERA_VERSION=dev
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VERA_VERSION=${VERA_VERSION}
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin vera
# Writable state lives in a volume mounted here; the rest of the file system is read-only.
RUN mkdir -p /state && chown vera /state
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY vera ./vera
COPY api ./api
COPY ml ./ml
COPY web ./web
USER vera
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/v1/health', timeout=2)"]
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
