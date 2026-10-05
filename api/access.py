"""Access to the demo: a login for the jury and the team, so nobody else spends the language model.

Accounts live in VERA_TESTERS as "user:hash,user:hash", where each hash is PBKDF2-SHA256 with its own salt; the plain
password never reaches the server's configuration. Without accounts the demo stays open, as in development and tests.

Usage: python -m api.access <user>   (reads the password without echo and prints the entry for VERA_TESTERS)
"""

import base64
import getpass
import hashlib
import hmac
import secrets
import sys

ITERATIONS = 200_000
SCHEME = "pbkdf2_sha256"


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str, salt: bytes | None = None, iterations: int = ITERATIONS) -> str:
    """Dots separate the parts: a dollar sign would be read as a variable in the server's .env."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{SCHEME}.{iterations}.{_encode(salt)}.{_encode(digest)}"


def check_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt, digest = stored.split(".")
        expected = _decode(digest)
        computed = hashlib.pbkdf2_hmac("sha256", password.encode(), _decode(salt), int(iterations))
    except ValueError:
        return False
    return scheme == SCHEME and hmac.compare_digest(computed, expected)


# Checked when the user does not exist, so an unknown name takes as long as a wrong password.
_DECOY = hash_password(secrets.token_hex(16))


class Accounts:
    def __init__(self, configured: str) -> None:
        entries = (entry.strip().split(":", 1) for entry in configured.split(",") if ":" in entry)
        self._hashes = {user.strip(): stored.strip() for user, stored in entries if user.strip()}

    @property
    def open(self) -> bool:
        """No accounts configured: the demo needs no login, as before."""
        return not self._hashes

    def check(self, username: str, password: str) -> bool:
        stored = self._hashes.get(username)
        if stored is None:
            check_password(password, _DECOY)
            return False
        return check_password(password, stored)


if __name__ == "__main__":
    if len(sys.argv) != 2 or ":" in sys.argv[1] or "," in sys.argv[1]:
        sys.exit("usage: python -m api.access <user>  (the user name cannot contain ':' or ',')")
    password = getpass.getpass("Password: ")
    if len(password) < 12:
        sys.exit("use at least 12 characters")
    print(f"{sys.argv[1]}:{hash_password(password)}")
