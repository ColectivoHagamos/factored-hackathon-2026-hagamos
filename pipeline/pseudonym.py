"""Keyed pseudonyms (HMAC-SHA256) for the identifiers of the public demo.

The key lives only on the machine that builds the demo subset, outside the repository: never in the repository,
the CI or the server. Without the key a pseudonym cannot be traced back to the original identifier.
"""

import hashlib
import hmac
import os
import secrets
from pathlib import Path

from pipeline.paths import REPO, ensure_outside_repo

PREFIXES = {"customer": "CUS", "product": "PRD", "transaction": "TRX", "complaint": "DSP"}


def key_path() -> Path:
    return Path(os.environ.get("VERA_PSEUDONYM_KEY_FILE") or REPO.parent / "secrets" / "vera_pseudonym.key")


def load_or_create_key(path: Path) -> bytes:
    """Read the key, or create a random 256-bit key readable only by its owner."""
    path = ensure_outside_repo(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(secrets.token_hex(32))
    return bytes.fromhex(path.read_text(encoding="utf-8").strip())


def digest(key: bytes, kind: str, value: str) -> str:
    return hmac.new(key, f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()


def pseudonym(key: bytes, kind: str, value: str) -> str:
    """Stable pseudonym such as CUS-3F9A1C0B7D2E4A68 for one key; another key gives another pseudonym."""
    return f"{PREFIXES[kind]}-{digest(key, kind, value)[:16].upper()}"


def invented_last4(key: bytes, product_id: str) -> str:
    """Four invented digits for a masked card; they are not the digits of the real card."""
    return f"{int(digest(key, 'card', product_id)[:8], 16) % 10_000:04d}"
