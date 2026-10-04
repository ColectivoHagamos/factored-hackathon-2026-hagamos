"""Pruebas del verificador de publicación sobre repositorios git temporales."""

import subprocess
from pathlib import Path

import pytest

from scripts.verificar_publicacion import luhn_valido, verificar


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Prueba")
    _git(tmp_path, "config", "user.email", "prueba@example.com")
    (tmp_path / "README.md").write_text("# Proyecto\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "inicio")
    return tmp_path


def _tipos(repo: Path) -> set[str]:
    return {h.tipo for h in verificar(repo)}


def test_repo_limpio_no_tiene_hallazgos(repo: Path):
    assert verificar(repo) == []


RUTAS_PROHIBIDAS = [
    "muestra.csv",
    "data/clientes.txt",
    "casos.db",
    "modelo.joblib",
    ".env",
    "LATAM_Data_Dictionary.pdf",
]


@pytest.mark.parametrize("ruta", RUTAS_PROHIBIDAS)
def test_rutas_prohibidas(repo: Path, ruta: str):
    archivo = repo / ruta
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text("x", encoding="utf-8")
    assert "archivo prohibido" in _tipos(repo)


def test_env_example_esta_permitido(repo: Path):
    (repo / ".env.example").write_text("LLM_API_KEY=\n", encoding="utf-8")
    assert verificar(repo) == []


@pytest.mark.parametrize(
    ("contenido", "tipo"),
    [
        ("clave = 'AKIA" + "ABCDEFGHIJKLMNOP'", "llave de acceso de AWS"),
        ("-----BEGIN RSA " + "PRIVATE KEY-----", "llave privada"),
        ("bucket = 's3://" + "datos-reales-123/'", "URI de S3 con nombre de bucket"),
        ("tel: +57 300 " + "123 4567", "teléfono con el formato del dataset"),
        ("correo: cliente@" + "correo.co", "dirección de correo"),
        ("tarjeta 4111" + "111111111111", "número de tarjeta válido (Luhn)"),
    ],
)
def test_secretos_y_datos_personales(repo: Path, contenido: str, tipo: str):
    (repo / "config.py").write_text(contenido + "\n", encoding="utf-8")
    assert tipo in _tipos(repo)


def test_marcadores_permitidos(repo: Path):
    (repo / "docs.md").write_text("s3://$BUCKET/ · contacto@example.com · " + "1234" * 4 + "\n", encoding="utf-8")
    assert verificar(repo) == []


def test_secreto_borrado_sigue_en_el_historial(repo: Path):
    (repo / "config.py").write_text("clave = 'AKIA" + "ABCDEFGHIJKLMNOP'\n", encoding="utf-8")
    _git(repo, "add", "config.py")
    _git(repo, "commit", "-q", "-m", "agrega config")
    (repo / "config.py").unlink()
    _git(repo, "commit", "-q", "-am", "quita config")
    hallazgos = verificar(repo)
    assert [(h.tipo, h.ubicacion) for h in hallazgos] == [("llave de acceso de AWS", "historial")]


def test_archivo_grande(repo: Path):
    (repo / "pesado.bin").write_bytes(b"0" * (10 * 1024 * 1024 + 1))
    assert "archivo de más de 10 MB" in _tipos(repo)


def test_luhn():
    assert luhn_valido("4111" + "1111" * 3)
    assert not luhn_valido("1234" + "5678" + "9012" + "3456")
