"""Tests of the publication check on temporary git repositories."""

import subprocess
from pathlib import Path

import pytest

from scripts.check_publication import check, luhn_valid


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "user.email", "test@example.com")
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def _kinds(repo: Path) -> set[str]:
    return {finding.kind for finding in check(repo)}


def test_clean_repo_has_no_findings(repo: Path):
    assert check(repo) == []


FORBIDDEN_PATHS = [
    "sample.csv",
    "data/customers.txt",
    "cases.db",
    "model.joblib",
    ".env",
    "LATAM_Data_Dictionary.pdf",
]


@pytest.mark.parametrize("path", FORBIDDEN_PATHS)
def test_forbidden_paths(repo: Path, path: str):
    file = repo / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("x", encoding="utf-8")
    assert "forbidden file" in _kinds(repo)


def test_env_example_is_allowed(repo: Path):
    (repo / ".env.example").write_text("LLM_API_KEY=\n", encoding="utf-8")
    assert check(repo) == []


@pytest.mark.parametrize(
    ("content", "kind"),
    [
        ("key = 'AKIA" + "ABCDEFGHIJKLMNOP'", "AWS access key"),
        ("-----BEGIN RSA " + "PRIVATE KEY-----", "private key"),
        ("bucket = 's3://" + "real-data-123/'", "S3 URI with a bucket name"),
        ("phone: +57 300 " + "123 4567", "phone number in the dataset format"),
        ("email: customer@" + "mail.co", "email address"),
        ("card 4111" + "111111111111", "valid card number (Luhn)"),
    ],
)
def test_secrets_and_personal_data(repo: Path, content: str, kind: str):
    (repo / "config.py").write_text(content + "\n", encoding="utf-8")
    assert kind in _kinds(repo)


def test_allowed_placeholders(repo: Path):
    (repo / "docs.md").write_text("s3://$BUCKET/ · contact@example.com · " + "1234" * 4 + "\n", encoding="utf-8")
    assert check(repo) == []


def test_deleted_secret_remains_in_history(repo: Path):
    (repo / "config.py").write_text("key = 'AKIA" + "ABCDEFGHIJKLMNOP'\n", encoding="utf-8")
    _git(repo, "add", "config.py")
    _git(repo, "commit", "-q", "-m", "add config")
    (repo / "config.py").unlink()
    _git(repo, "commit", "-q", "-am", "remove config")
    assert [(f.kind, f.location) for f in check(repo)] == [("AWS access key", "history")]


def test_decorators_in_history_are_not_emails(repo: Path):
    content = "\n".join(["import pytest", "", "", "@pytest.fixture", "def f():", "    return 1", ""])
    (repo / "test_x.py").write_text(content, encoding="utf-8")
    _git(repo, "add", "test_x.py")
    _git(repo, "commit", "-q", "-m", "add test")
    assert check(repo) == []


def test_real_email_in_history(repo: Path):
    (repo / "contact.txt").write_text("write to support@" + "bank.co\n", encoding="utf-8")
    _git(repo, "add", "contact.txt")
    _git(repo, "commit", "-q", "-m", "add contact")
    (repo / "contact.txt").unlink()
    _git(repo, "commit", "-q", "-am", "remove contact")
    assert [(f.kind, f.location) for f in check(repo)] == [("email address", "history")]


def test_large_file(repo: Path):
    (repo / "heavy.bin").write_bytes(b"0" * (10 * 1024 * 1024 + 1))
    assert "file larger than 10 MB" in _kinds(repo)


def test_luhn():
    assert luhn_valid("4111" + "1111" * 3)
    assert not luhn_valid("1234" + "5678" + "9012" + "3456")
