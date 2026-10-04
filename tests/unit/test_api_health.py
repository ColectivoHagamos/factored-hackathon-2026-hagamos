"""Tests of the API skeleton: health endpoint, OpenAPI under /v1 and fail-fast settings."""

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.settings import Settings
from vera.contracts.api import HealthResponse


def client(**settings: str) -> TestClient:
    return TestClient(create_app(Settings(**settings)))


def test_health_reports_status_interpreter_and_version():
    response = client(llm="rules", version="abc1234").get("/v1/health")
    assert response.status_code == 200
    assert HealthResponse.model_validate(response.json()) == HealthResponse(
        status="ok", llm_provider="rules", version="abc1234"
    )


def test_openapi_is_served_under_the_versioned_prefix():
    paths = client().get("/v1/openapi.json").json()["paths"]
    assert "/v1/health" in paths


def test_defaults_need_no_configuration():
    defaults = Settings.from_env({})
    assert (defaults.adapter, defaults.llm, defaults.version, defaults.state_db) == ("mock", "rules", "dev", ":memory:")
    # Without configuration each start gets its own random secrets.
    assert defaults.session_secret != Settings.from_env({}).session_secret
    assert Settings.from_env({"VERA_ADAPTER": "", "VERA_LLM": ""}).adapter == "mock"


@pytest.mark.parametrize("env", [{"VERA_ADAPTER": "production_db"}, {"VERA_LLM": "gpt"}])
def test_unknown_configuration_stops_the_start_up(env: dict):
    with pytest.raises(ValueError, match="must be one of"):
        Settings.from_env(env)
