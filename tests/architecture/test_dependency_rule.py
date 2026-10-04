"""Hexagonal architecture dependency rule: the domain does not know the infrastructure.

The domain (contracts, ports, core, policy and output) may only import the standard library,
Pydantic and other domain modules. This keeps the rules unchanged when the LLM, the database or the bank
changes, and lets the domain be tested without network or data.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAIN = ["vera/contracts", "vera/ports", "vera/core", "vera/policy", "vera/output"]

# Infrastructure the domain must not import: external libraries and outer layers of this repo.
FORBIDDEN = {
    "fastapi",
    "starlette",
    "uvicorn",
    "httpx",
    "requests",
    "duckdb",
    "sqlite3",
    "anthropic",
    "openai",
    "sklearn",
    "boto3",
    "api",
    "vera.adapters",
    "vera.llm",
    "vera.gateway",
    "vera.tools",
    "pipeline",
    "ml",
    "evaluation",
}


def imported_modules(code: str) -> set[str]:
    """Return the fully qualified names of the modules imported by a Python source file."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def forbidden_imports(code: str) -> set[str]:
    """Return the imported modules that belong to infrastructure forbidden for the domain."""
    return {m for m in imported_modules(code) if any(m == f or m.startswith(f + ".") for f in FORBIDDEN)}


def test_detector_finds_forbidden_imports():
    code = "import duckdb\nfrom fastapi import FastAPI\nfrom vera.adapters.mock import Something\nimport json\n"
    assert forbidden_imports(code) == {"duckdb", "fastapi", "vera.adapters.mock"}


def test_detector_accepts_domain_and_standard_library():
    code = "from datetime import date\nfrom pydantic import BaseModel\nfrom vera.ports import Cases\n"
    assert forbidden_imports(code) == set()


def test_domain_does_not_import_infrastructure():
    violations = {
        str(path.relative_to(ROOT)): sorted(found)
        for folder in DOMAIN
        for path in (ROOT / folder).rglob("*.py")
        if (found := forbidden_imports(path.read_text(encoding="utf-8")))
    }
    assert violations == {}, f"The domain imports infrastructure: {violations}"
