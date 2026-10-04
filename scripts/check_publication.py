"""Check that the repository can be published: no data, secrets, forbidden files or large files.

Scans the working tree (tracked files and new files that are not ignored) and the whole git history.
It never prints a matched value, only the finding type and its location. Exits with code 1 on any finding.

Usage: python scripts/check_publication.py [--repo PATH]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MAX_BYTES = 10 * 1024 * 1024

FORBIDDEN_PATHS = re.compile(
    r"(^|/)(data|data_lake|demo)/"
    r"|\.(csv|parquet|duckdb|feather|arrow|db|sqlite|sqlite3|db-journal|pkl|pickle|joblib|pem|key)$"
    r"|(^|/)\.env(\.(?!example$)[^/]*)?$"
    r"|(^|/)\.aws/"
    r"|credentials"
    r"|Data_Dictionary",
    re.IGNORECASE,
)

SECRETS = {
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "assigned AWS secret": re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*['\"]?[A-Za-z0-9/+]{30,}"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "API key with sk- prefix": re.compile(r"\bsk-[A-Za-z0-9_-]{24,}"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{50,})\b"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "AWS ARN": re.compile(r"arn:aws:[a-z0-9-]+:"),
    "S3 URI with a bucket name": re.compile(r"s3://(?![$<{])[a-z0-9][a-z0-9.\-]{2,}"),
}

PHONE = re.compile(r"\+\d{2} \d{3} \d{3} \d{4}")
# Length-bounded parts (RFC 5321) keep the search linear. The local part starts with a letter or digit,
# so a diff line such as "+@decorator.attribute" is not mistaken for an email address.
EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9][A-Za-z0-9._%+-]{0,63}@(?:[A-Za-z0-9-]{1,63}\.){1,8}[A-Za-z]{2,24}"
)
ALLOWED_DOMAINS = ("example.com", "example.org", "ejemplo.com", "ejemplo.org")
PAN_CANDIDATE = re.compile(r"(?<!\d)[3-6]\d{12,18}(?!\d)")
BINARY_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".woff", ".woff2", ".zip")


@dataclass(frozen=True)
class Finding:
    kind: str
    location: str


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, errors="replace")
    return result.stdout


def luhn_valid(number: str) -> bool:
    """Return whether the number passes the Luhn check digit, as real card numbers do."""
    total = 0
    for position, digit in enumerate(int(d) for d in reversed(number)):
        if position % 2 == 1:
            digit = digit * 2 - 9 if digit > 4 else digit * 2
        total += digit
    return total % 10 == 0


def findings_in_text(text: str, location: str) -> list[Finding]:
    """Return secrets and personal data found in a text; matched values are never kept."""
    findings = [Finding(kind, location) for kind, pattern in SECRETS.items() if pattern.search(text)]
    if PHONE.search(text):
        findings.append(Finding("phone number in the dataset format", location))
    if any(not m.group(0).lower().endswith(ALLOWED_DOMAINS) for m in EMAIL.finditer(text)):
        findings.append(Finding("email address", location))
    if any(luhn_valid(m.group(0)) for m in PAN_CANDIDATE.finditer(text)):
        findings.append(Finding("valid card number (Luhn)", location))
    return findings


def tree_files(repo: Path) -> list[str]:
    output = git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    return [path for path in output.split("\0") if path and (repo / path).is_file()]


def scan_tree(repo: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in tree_files(repo):
        file = repo / path
        if FORBIDDEN_PATHS.search(path):
            findings.append(Finding("forbidden file", path))
        if file.stat().st_size > MAX_BYTES:
            findings.append(Finding("file larger than 10 MB", path))
            continue
        if not path.lower().endswith(BINARY_EXTENSIONS):
            findings += findings_in_text(file.read_text(encoding="utf-8", errors="replace"), path)
    return findings


def scan_history(repo: Path) -> list[Finding]:
    findings: list[Finding] = []
    objects = git(repo, "rev-list", "--objects", "--all").splitlines()
    paths = sorted({line.split(" ", 1)[1] for line in objects if " " in line})
    findings += [Finding("forbidden file in history", p) for p in paths if FORBIDDEN_PATHS.search(p)]
    omitted = git(repo, "rev-list", "--objects", "--all", "--filter=blob:limit=10m", "--filter-print-omitted")
    large = [line[1:] for line in omitted.splitlines() if line.startswith("~")]
    findings += [Finding("file larger than 10 MB in history", obj) for obj in large]
    diffs = git(repo, "log", "--all", "-p", "--no-color", "--format=commit %h")
    findings += findings_in_text(diffs, "history")
    return findings


def check(repo: Path) -> list[Finding]:
    seen: dict[tuple[str, str], Finding] = {}
    for finding in scan_tree(repo) + scan_history(repo):
        seen.setdefault((finding.kind, finding.location), finding)
    return list(seen.values())


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that the repository can be published.")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    repo = parser.parse_args().repo.resolve()
    findings = check(repo)
    for finding in findings:
        print(f"FAIL  {finding.kind}: {finding.location}")
    print(f"Result: {len(findings)} finding(s)." if findings else "Result: no findings.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
