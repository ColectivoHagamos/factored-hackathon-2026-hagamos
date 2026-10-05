# ADR 0007 · Session tokens are JSON Web Tokens

**Date:** 2026-10-05 · **Status:** accepted

## Context

Three sessions exist: the access session after the login, a demo customer session and the analyst session. Each was a signed token in a format of our own. A bank's identity provider issues standard tokens, and a reviewer reads a standard format faster.

## Decision

1. Every session token is a JSON Web Token (RFC 7519) signed with HS256, issued and verified with PyJWT in `api/security.py`.
2. The claims are `iss` (`vera`), `sub`, `role` (`tester`, `customer` or `analyst`), `iat`, `exp` and a random `jti`; all but `jti` are required.
3. Only HS256 is accepted, so a token that names another algorithm, or `none`, is rejected before its claims are read.
4. The signing key is derived from `SESSION_SECRET` with SHA-256, so it always has the 256 bits HS256 expects.
5. Expiry is checked against the application clock, the same one the conversation uses. Lifetimes do not change: eight hours for the access session and fifteen minutes for a customer session.

## Rejected alternatives

| Alternative | Reason |
|---|---|
| Keep the format of our own | Same security, but a reviewer or an identity provider has to learn it |
| Asymmetric signatures (RS256 or EdDSA) | One service issues and verifies the tokens; a key pair adds rotation work with no reader that needs the public key |
| Tokens in cookies | The API is called with a bearer token by the web and by tests alike; the strict Content-Security-Policy limits script injection, and the web keeps tokens in session storage only |

## Consequences

- Tokens issued before the change stop working; users simply log in again.
- `tests/unit/test_session_tokens.py` covers the format, a forged signature, the `none` algorithm, a tampered role, a foreign key, expiry and garbage input.
