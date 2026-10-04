"""Verifica que el repositorio se pueda publicar: sin datos, secretos, archivos prohibidos ni archivos grandes.

Revisa el árbol de trabajo (archivos rastreados y nuevos no ignorados) y todo el historial de git.
Nunca imprime un valor encontrado: solo el tipo de hallazgo y la ruta. Sale con código 1 si hay hallazgos.

Uso: python scripts/verificar_publicacion.py [--repo RUTA]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

LIMITE_BYTES = 10 * 1024 * 1024

RUTAS_PROHIBIDAS = re.compile(
    r"(^|/)(data|data_lake|demo)/"
    r"|\.(csv|parquet|duckdb|feather|arrow|db|sqlite|sqlite3|db-journal|pkl|pickle|joblib|pem|key)$"
    r"|(^|/)\.env(\.(?!example$)[^/]*)?$"
    r"|(^|/)\.aws/"
    r"|credentials"
    r"|Data_Dictionary",
    re.IGNORECASE,
)

SECRETOS = {
    "llave de acceso de AWS": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "secreto de AWS asignado": re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*['\"]?[A-Za-z0-9/+]{30,}"),
    "llave privada": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "llave de API con prefijo sk-": re.compile(r"\bsk-[A-Za-z0-9_-]{24,}"),
    "token de GitHub": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{50,})\b"),
    "token de Slack": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "llave de Google": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "ARN de AWS": re.compile(r"arn:aws:[a-z0-9-]+:"),
    "URI de S3 con nombre de bucket": re.compile(r"s3://(?![$<{])[a-z0-9][a-z0-9.\-]{2,}"),
}

TELEFONO = re.compile(r"\+\d{2} \d{3} \d{3} \d{4}")
# Partes con largo acotado (RFC 5321) para que la búsqueda sea lineal también en archivos grandes
EMAIL = re.compile(r"[A-Za-z0-9._%+-]{1,64}@(?:[A-Za-z0-9-]{1,63}\.){1,8}[A-Za-z]{2,24}")
DOMINIOS_PERMITIDOS = ("example.com", "example.org", "ejemplo.com", "ejemplo.org")
CANDIDATO_PAN = re.compile(r"(?<!\d)[3-6]\d{12,18}(?!\d)")
EXTENSIONES_BINARIAS = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".woff", ".woff2", ".zip")


@dataclass(frozen=True)
class Hallazgo:
    tipo: str
    ubicacion: str


def git(repo: Path, *args: str) -> str:
    resultado = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, errors="replace")
    return resultado.stdout


def luhn_valido(numero: str) -> bool:
    """Indica si el número cumple el dígito verificador de Luhn, como las tarjetas reales."""
    suma = 0
    for posicion, digito in enumerate(int(d) for d in reversed(numero)):
        if posicion % 2 == 1:
            digito = digito * 2 - 9 if digito > 4 else digito * 2
        suma += digito
    return suma % 10 == 0


def hallazgos_en_texto(texto: str, ubicacion: str) -> list[Hallazgo]:
    """Secretos y datos personales en un texto; nunca se guarda el valor encontrado."""
    hallazgos = [Hallazgo(tipo, ubicacion) for tipo, patron in SECRETOS.items() if patron.search(texto)]
    if TELEFONO.search(texto):
        hallazgos.append(Hallazgo("teléfono con el formato del dataset", ubicacion))
    if any(not m.group(0).lower().endswith(DOMINIOS_PERMITIDOS) for m in EMAIL.finditer(texto)):
        hallazgos.append(Hallazgo("dirección de correo", ubicacion))
    if any(luhn_valido(m.group(0)) for m in CANDIDATO_PAN.finditer(texto)):
        hallazgos.append(Hallazgo("número de tarjeta válido (Luhn)", ubicacion))
    return hallazgos


def archivos_del_arbol(repo: Path) -> list[str]:
    salida = git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    return [ruta for ruta in salida.split("\0") if ruta and (repo / ruta).is_file()]


def revisar_arbol(repo: Path) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for ruta in archivos_del_arbol(repo):
        archivo = repo / ruta
        if RUTAS_PROHIBIDAS.search(ruta):
            hallazgos.append(Hallazgo("archivo prohibido", ruta))
        if archivo.stat().st_size > LIMITE_BYTES:
            hallazgos.append(Hallazgo("archivo de más de 10 MB", ruta))
            continue
        if not ruta.lower().endswith(EXTENSIONES_BINARIAS):
            hallazgos += hallazgos_en_texto(archivo.read_text(encoding="utf-8", errors="replace"), ruta)
    return hallazgos


def revisar_historial(repo: Path) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    objetos = git(repo, "rev-list", "--objects", "--all").splitlines()
    rutas = sorted({linea.split(" ", 1)[1] for linea in objetos if " " in linea})
    hallazgos += [Hallazgo("archivo prohibido en el historial", r) for r in rutas if RUTAS_PROHIBIDAS.search(r)]
    omitidos = git(repo, "rev-list", "--objects", "--all", "--filter=blob:limit=10m", "--filter-print-omitted")
    grandes = [linea[1:] for linea in omitidos.splitlines() if linea.startswith("~")]
    hallazgos += [Hallazgo("archivo de más de 10 MB en el historial", objeto) for objeto in grandes]
    diferencias = git(repo, "log", "--all", "-p", "--no-color", "--format=commit %h")
    hallazgos += hallazgos_en_texto(diferencias, "historial")
    return hallazgos


def verificar(repo: Path) -> list[Hallazgo]:
    vistos: dict[tuple[str, str], Hallazgo] = {}
    for hallazgo in revisar_arbol(repo) + revisar_historial(repo):
        vistos.setdefault((hallazgo.tipo, hallazgo.ubicacion), hallazgo)
    return list(vistos.values())


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica que el repositorio se pueda publicar.")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    repo = parser.parse_args().repo.resolve()
    hallazgos = verificar(repo)
    for hallazgo in hallazgos:
        print(f"FALLA  {hallazgo.tipo}: {hallazgo.ubicacion}")
    print(f"Resultado: {len(hallazgos)} hallazgo(s)." if hallazgos else "Resultado: sin hallazgos.")
    return 1 if hallazgos else 0


if __name__ == "__main__":
    sys.exit(main())
