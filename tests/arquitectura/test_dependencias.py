"""Regla de dependencias de la arquitectura hexagonal: el dominio no conoce la infraestructura.

El dominio (contratos, puertos, núcleo, política y salida) solo puede importar la biblioteca estándar,
Pydantic y otros módulos del dominio. Así se cambia de LLM, de base de datos o de banco sin tocar las reglas,
y el dominio se prueba sin red ni datos.
"""

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOMINIO = ["agente/contratos", "agente/puertos", "agente/nucleo", "agente/politica", "agente/salida"]

# Infraestructura que el dominio no puede importar (bibliotecas externas y capas exteriores del propio repo)
PROHIBIDOS = {
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
    "agente.adaptadores",
    "agente.llm",
    "agente.gateway",
    "agente.herramientas",
    "pipeline",
    "ml",
    "evaluacion",
}


def modulos_importados(codigo: str) -> set[str]:
    """Nombres completos de los módulos que importa un archivo de Python."""
    nombres: set[str] = set()
    for nodo in ast.walk(ast.parse(codigo)):
        if isinstance(nodo, ast.Import):
            nombres.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            nombres.add(nodo.module)
    return nombres


def importaciones_prohibidas(codigo: str) -> set[str]:
    """Módulos importados que pertenecen a la infraestructura prohibida para el dominio."""
    return {m for m in modulos_importados(codigo) if any(m == p or m.startswith(p + ".") for p in PROHIBIDOS)}


def test_el_detector_encuentra_una_importacion_prohibida():
    codigo = "import duckdb\nfrom fastapi import FastAPI\nfrom agente.adaptadores.mock import Algo\nimport json\n"
    assert importaciones_prohibidas(codigo) == {"duckdb", "fastapi", "agente.adaptadores.mock"}


def test_el_detector_acepta_dominio_y_biblioteca_estandar():
    codigo = "from datetime import date\nfrom pydantic import BaseModel\nfrom agente.puertos import Casos\n"
    assert importaciones_prohibidas(codigo) == set()


def test_el_dominio_no_importa_infraestructura():
    violaciones = {
        str(archivo.relative_to(RAIZ)): sorted(prohibidas)
        for carpeta in DOMINIO
        for archivo in (RAIZ / carpeta).rglob("*.py")
        if (prohibidas := importaciones_prohibidas(archivo.read_text(encoding="utf-8")))
    }
    assert violaciones == {}, f"El dominio importa infraestructura: {violaciones}"
