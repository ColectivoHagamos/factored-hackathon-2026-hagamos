"""Session tokens as JSON Web Tokens (RFC 7519) signed with HS256. The demo issues them for a chosen demo customer;
in production the bank's identity provider does. A document number never opens a session."""

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt

SESSION_TTL = timedelta(minutes=15)
# An access session lasts a working session; each demo customer session still lasts 15 minutes.
ACCESS_TTL = timedelta(hours=8)
ISSUER = "vera"
# The only algorithm accepted: a token that names another one, or "none", is rejected before its claims are read.
ALGORITHM = "HS256"


class InvalidSessionError(Exception):
    """The token is missing, forged or expired."""


@dataclass(frozen=True)
class SessionToken:
    subject: str
    role: str
    expires_at: datetime


@dataclass(frozen=True)
class IssuedToken:
    token: str
    expires_at: datetime


class SessionSigner:
    def __init__(self, secret: str, now: Callable[[], datetime]) -> None:
        # A fixed-length key derived from the configured secret, as HS256 expects (RFC 7518, section 3.2).
        self._key = hashlib.sha256(b"vera-session:" + secret.encode()).digest()
        self._now = now

    def issue(self, subject: str, role: str = "customer", ttl: timedelta = SESSION_TTL) -> IssuedToken:
        """The token and the moment it expires, from one clock, so the web and the API never disagree."""
        issued_at = self._now()
        claims = {
            "iss": ISSUER,
            "sub": subject,
            "role": role,
            "iat": int(issued_at.timestamp()),
            "exp": int((issued_at + ttl).timestamp()),
            "jti": secrets.token_hex(8),
        }
        token = jwt.encode(claims, self._key, algorithm=ALGORITHM)
        return IssuedToken(token, datetime.fromtimestamp(claims["exp"], tz=issued_at.tzinfo).astimezone())

    def verify(self, token: str, role: str = "customer") -> SessionToken:
        try:
            claims = jwt.decode(
                token,
                self._key,
                algorithms=[ALGORITHM],
                issuer=ISSUER,
                # Time is checked against the injected clock below, so tests and replays use one notion of now.
                options={"require": ["iss", "sub", "role", "iat", "exp"], "verify_exp": False, "verify_iat": False},
            )
        except jwt.InvalidTokenError as error:
            raise InvalidSessionError("malformed or forged token") from error
        expires_at = datetime.fromtimestamp(claims["exp"], tz=self._now().tzinfo)
        if claims["role"] != role or self._now() >= expires_at:
            raise InvalidSessionError("expired or wrong role")
        return SessionToken(claims["sub"], claims["role"], expires_at)
