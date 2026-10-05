"""Export the JSON Schema of every public boundary model to docs/schemas.

Usage: python -m scripts.export_schemas [--check]
With --check nothing is written, and the exit code is 1 when the files differ from the models.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import BaseModel

from vera.contracts import api, cases, charges, events, handoff, interpretation, legal
from vera.contracts.tools import TOOL_INPUTS, TOOL_OUTPUTS, ToolError

TARGET = Path(__file__).resolve().parents[1] / "docs" / "schemas"

MODELS: dict[str, type[BaseModel]] = {
    "interpretation": interpretation.Interpretation,
    "candidate": charges.Candidate,
    "charge_detail": charges.ChargeDetail,
    "case": cases.Case,
    "event": events.Event,
    "handoff": handoff.Handoff,
    "transfer": handoff.Transfer,
    "legal_rule": legal.LegalRule,
    "tool_error": ToolError,
    **{f"tool_{name}_input": model for name, model in TOOL_INPUTS.items()},
    **{f"tool_{name}_output": model for name, model in TOOL_OUTPUTS.items()},
    "api_login_request": api.LoginRequest,
    "api_login_response": api.LoginResponse,
    "api_demo_session_request": api.DemoSessionRequest,
    "api_demo_session_response": api.DemoSessionResponse,
    "api_start_conversation_request": api.StartConversationRequest,
    "api_start_conversation_response": api.StartConversationResponse,
    "api_message_request": api.MessageRequest,
    "api_message_response": api.MessageResponse,
    "api_me_response": api.MeResponse,
    "api_movement": api.Movement,
    "api_case_view": api.CaseView,
    "api_health_response": api.HealthResponse,
    "api_metrics_response": api.MetricsResponse,
    "api_queue_item": api.QueueItem,
    "api_error": api.ApiError,
}


def render(model: type[BaseModel]) -> str:
    return json.dumps(model.model_json_schema(), indent=2, ensure_ascii=False) + "\n"


def expected_files() -> dict[str, str]:
    return {f"{name}.json": render(model) for name, model in MODELS.items()}


def differences(files: dict[str, str]) -> list[str]:
    """Return the files that are missing, outdated or no longer produced by any model."""
    stale = [name for name, text in files.items() if not _matches(TARGET / name, text)]
    orphans = [path.name for path in TARGET.glob("*.json") if path.name not in files]
    return sorted(stale + orphans)


def _matches(path: Path, text: str) -> bool:
    return path.is_file() and path.read_text(encoding="utf-8") == text


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the JSON Schema of the boundary models.")
    parser.add_argument("--check", action="store_true", help="only report differences")
    files = expected_files()
    if parser.parse_args().check:
        pending = differences(files)
        for name in pending:
            print(f"OUTDATED  docs/schemas/{name}")
        print("Result: schemas are up to date." if not pending else "Run: python -m scripts.export_schemas")
        return 1 if pending else 0
    TARGET.mkdir(parents=True, exist_ok=True)
    for path in TARGET.glob("*.json"):
        if path.name not in files:
            path.unlink()
    for name, text in files.items():
        (TARGET / name).write_text(text, encoding="utf-8")
    print(f"Exported {len(files)} schemas to docs/schemas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
