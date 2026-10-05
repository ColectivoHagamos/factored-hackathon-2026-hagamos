# ADR 0005 · A login keeps the demo for the jury

**Date:** 2026-10-05 · **Status:** accepted

## Context

The public demo reads with a paid language model under a spending cap of US$ 15. Without a login, anyone with the URL could open a demo customer and spend the cap, or fill the analyst queue. The challenge asks for a demo that a reviewer can open, and the jury receives the submission by email.

## Decision

1. **Accounts for the jury and the team,** read from `VERA_TESTERS` as `user:hash`. Each hash is PBKDF2-SHA256 with its own salt and 200,000 iterations; the plain password never reaches the server's configuration or the repository, and it travels only in the submission email.
2. **`POST /v1/auth/login` issues an access token** signed like the customer sessions, for eight hours. The demo customers, a demo session and the analyst session ask for it. A conversation still needs the customer's own 15-minute session: the access token never stands for a customer.
3. **An unknown user takes as long as a wrong password,** and an address gets ten attempts per minute.
4. **Without accounts the demo stays open,** as in development, the tests and the evaluation.

## Rejected alternatives

| Alternative | Reason |
|---|---|
| No login, only the spending cap | One stranger could end the demo for the jury by spending the cap |
| Basic authentication at Caddy | A browser prompt instead of a page, and the API tests against the URL would need another path |
| An identity provider (OAuth) | The right answer for a bank, but days of work and an external dependency for a two-week demo |

## Consequences

- The jury needs the credentials from the submission email; the README says so.
- The end-to-end suite logs in against a closed deployment with `VERA_E2E_LOGIN`.
- A real deployment would replace the accounts with the bank's identity provider, as SECURITY.md states.
