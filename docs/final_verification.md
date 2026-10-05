# Final verification

What a reviewer will open, checked against the public deployment on 4 October 2026 at 22:00 in Colombia (5 October, 03:00 UTC), with `production` at `2350e69`.

## The deployment

| Check | Result |
|---|---|
| `dig +short vera.colectivohagamos.com` | `3.93.170.171`, the demo server |
| `curl -I http://vera.colectivohagamos.com/` | `308 Permanent Redirect` to `https://` |
| Certificate | Let's Encrypt, for `vera.colectivohagamos.com`, valid until 2 January 2027 |
| Security headers | `Strict-Transport-Security`, `Content-Security-Policy` (`default-src 'self'`, `frame-ancestors 'none'`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy` |
| `GET /v1/health` | `ok`, with `llm_provider: anthropic` and the version `2350e69`, the commit in `production` |
| Continuous deployment of `2350e69` | Image built and pushed, deployment with rollback, public health check: all passed |

## The end-to-end suite against the URL

```bash
VERA_E2E_URL=https://vera.colectivohagamos.com uv run --frozen pytest tests/e2e
```

**12 of 12 pass**, with Claude reading over the classifier. Each test talks only HTTP, as a customer and as the analyst. The 12 skipped are the in-memory variant with the classifier alone, which does not apply to a deployment.

| Scenario | What it proves at the URL |
|---|---|
| A1 | A purchase in Colombia: the charge is found, one case is registered and read back, and the deadline (CO-R15, Ley 1755) is dated with its source |
| A2 | A pending charge is explained and nothing is opened; if the customer still does not recognize it, it counts as a fraud signal |
| A3 | Without the card, the block is confirmed and read back, one case groups the charges, and Fraud gets the handoff with a network reason code |
| A4 | A charge in Madrid gets its route, with no invented date |
| A5 | A credit card dispute in Argentina gets the Ley 25.065 deadlines |
| A6 | Portuguese from the first message to the handoff |
| A7 | Injection and another customer's data answer "not found", and nothing changes |
| A8 | A request for a person wins over a pending confirmation |
| A9 | The customer chooses between two charges, and a side question does not cut the flow |
| A10 | An improper bank charge is identified, registered and sent to Complaints |
| Scam | VERA asks when and how, says a transfer has no chargeback, and Fraud gets the answers |

## As a reviewer, in a browser

The demo was opened in headless Chromium, as a reviewer would:

- the list offers 47 pseudonymized demo customers, each named with its scenario;
- the greeting says that VERA is an AI assistant;
- with a customer tagged A1, "No reconozco un cargo de mi tarjeta" gets the receipt of a charge and the question, with the Sí and No buttons;
- the analyst console lists the queue;
- no page or console error.

The page also refused to evaluate a script from text, as its Content Security Policy requires: the browser tool had to wait for elements instead.

Of the six messages in the README guide, the request for a person and the injection were tried by hand on the public chat:

- **"Quiero hablar con una persona":** one offer to review the case first; «No, quiero una persona» then passes the conversation to a person (POL-01).
- **The injection:** it gets "No encontré ese movimiento entre los suyos" and goes back to the open question (POL-03).

The other four are the openings of A1, A3, A6 and A10 above.

## Not verified here

- **The audit of the running container** (`docker exec <api> env` and `docker history`) runs on the server, which only the team reaches over SSH. By construction, the CD writes to the server's `.env`, readable only by its owner, five values: the session secret, the analyst key, and the language model's provider, key and workspace. The image is built in CI from this repository, which the publication audit checks.
