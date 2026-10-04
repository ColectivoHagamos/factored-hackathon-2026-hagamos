"""Signed session tokens. The demo issues them for a chosen demo customer; in production the bank's identity
provider does. A document number never opens a session."""

import base64
import hashlib
import hmac
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

SESSION_TTL = timedelta(minutes=15)


class InvalidSessionError(Exception):
    """The token is missing, forged or expired."""


@dataclass(frozen=True)
class SessionToken:
    subject: str
    role: str
    expires_at: datetime


class SessionSigner:
    def __init__(self, secret: str, now: Callable[[], datetime]) -> None:
        self._secret = secret.encode()
        self._now = now

    def issue(self, subject: str, role: str = "customer") -> str:
        expires_at = self._now() + SESSION_TTL
        payload = json.dumps({"sub": subject, "role": role, "exp": int(expires_at.timestamp())}, separators=(",", ":"))
        body = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
        return f"{body}.{self._sign(body)}"

    def verify(self, token: str, role: str = "customer") -> SessionToken:
        try:
            body, signature = token.split(".", 1)
            if not hmac.compare_digest(signature, self._sign(body)):
                raise InvalidSessionError("bad signature")
            claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        except (ValueError, json.JSONDecodeError) as error:
            raise InvalidSessionError("malformed token") from error
        expires_at = datetime.fromtimestamp(claims["exp"], tz=self._now().tzinfo)
        if claims.get("role") != role or self._now() > expires_at:
            raise InvalidSessionError("expired or wrong role")
        return SessionToken(claims["sub"], claims["role"], expires_at)

    def _sign(self, body: str) -> str:
        return hmac.new(self._secret, body.encode(), hashlib.sha256).hexdigest()
