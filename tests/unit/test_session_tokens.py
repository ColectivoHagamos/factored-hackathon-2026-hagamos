"""Session tokens are standard JSON Web Tokens that only VERA can sign, for one role and a limited time."""

import base64
import json
from datetime import datetime, timedelta

import jwt
import pytest

from api.security import ALGORITHM, ISSUER, InvalidSessionError, SessionSigner

NOW = datetime(2026, 6, 18, 9, 0)


def signer(secret: str = "a-long-secret-for-the-tests", now: datetime = NOW) -> SessionSigner:
    return SessionSigner(secret, lambda: now)


def segment(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")


def tampered(claims: dict) -> str:
    """A token VERA signed, whose payload was swapped for one with more privileges."""
    header, _, signature = signer().issue("CO-01").token.split(".")
    return f"{header}.{segment(claims)}.{signature}"


def test_a_token_is_a_signed_jwt_with_its_claims():
    token = signer().issue("CO-01", role="customer", ttl=timedelta(minutes=15)).token
    header = jwt.get_unverified_header(token)
    claims = jwt.decode(token, options={"verify_signature": False})
    assert header == {"alg": ALGORITHM, "typ": "JWT"}
    assert claims["iss"] == ISSUER and claims["sub"] == "CO-01" and claims["role"] == "customer"
    assert claims["exp"] - claims["iat"] == 15 * 60 and claims["jti"]
    session = signer().verify(token)
    assert session.subject == "CO-01" and session.role == "customer"


def test_two_tokens_for_the_same_subject_are_never_equal():
    assert signer().issue("CO-01").token != signer().issue("CO-01").token


@pytest.mark.parametrize(
    "forge",
    [
        # No signature at all: the "none" algorithm.
        lambda claims: f"{segment({'alg': 'none', 'typ': 'JWT'})}.{segment(claims)}.",
        # Signed with a key VERA does not hold.
        lambda claims: jwt.encode(claims, "another-key-of-thirty-two-bytes!", algorithm=ALGORITHM),
        # A valid token whose role was changed after signing.
        tampered,
    ],
    ids=["alg-none", "foreign-key", "tampered-role"],
)
def test_a_forged_token_is_rejected(forge):
    claims = {"iss": ISSUER, "sub": "CO-01", "role": "analyst", "iat": 0, "exp": 2**31 - 1}
    with pytest.raises(InvalidSessionError):
        signer().verify(forge(claims), role="analyst")


def test_a_token_opens_only_its_own_role():
    token = signer().issue("CO-01", role="customer").token
    with pytest.raises(InvalidSessionError):
        signer().verify(token, role="analyst")


def test_an_expired_token_is_rejected():
    token = signer().issue("CO-01", ttl=timedelta(minutes=15)).token
    later = signer(now=NOW + timedelta(minutes=15))
    with pytest.raises(InvalidSessionError):
        later.verify(token)


def test_a_token_of_another_deployment_is_rejected():
    token = signer(secret="secret-of-another-deployment").issue("CO-01").token
    with pytest.raises(InvalidSessionError):
        signer().verify(token)


@pytest.mark.parametrize("token", ["", "not-a-token", "a.b", "a.b.c.d"])
def test_garbage_is_rejected(token):
    with pytest.raises(InvalidSessionError):
        signer().verify(token)
