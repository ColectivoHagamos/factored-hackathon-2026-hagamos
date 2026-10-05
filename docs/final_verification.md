# Final verification

What a reviewer will open, checked against the public deployment on 5 October 2026 at 06:30 in Colombia (11:30 UTC), with `production` at `57cbbac`.

## The deployment

| Check | Result |
|---|---|
| `dig +short vera.colectivohagamos.com` | `3.93.170.171`, the demo server |
| `curl -I http://vera.colectivohagamos.com/` | `308 Permanent Redirect` to `https://` |
| Certificate | Let's Encrypt, for `vera.colectivohagamos.com`, valid until 2 January 2027 |
| Security headers | `Strict-Transport-Security`, `Content-Security-Policy` (`default-src 'self'`, `frame-ancestors 'none'`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy` |
| `GET /v1/health` | `ok`, with `llm_provider: anthropic` and the version `57cbbac`, the commit in `production` |
| Continuous deployment of `0dc8982` (release #97) and `57cbbac` (hotfix #98) | Image built and pushed, deployment with rollback, public health check: all passed |
| Pages | `/`, `/login`, `/clientes`, `/banca`, `/chat` and `/analista` answer with the web; `/console.html` redirects to `/analista`; a missing file or `/v1` route answers 404 in JSON |
| Access | Without the login, the demo customers answer 401. The demo account gets a JSON Web Token (HS256) that lasts eight hours; the previous account name is rejected |

## The end-to-end suite against the URL

```bash
VERA_E2E_URL=https://vera.colectivohagamos.com VERA_E2E_LOGIN="demo:<password>" uv run --frozen pytest tests/e2e
```

**12 of 12 pass**, with Claude reading over the classifier, through the login. Each test talks only HTTP, as a customer and as the analyst. The 12 skipped are the in-memory variant with the classifier alone, which does not apply to a deployment.

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

## The product web, in a browser

The web was walked in Chromium at 1280 and 390 px, under the Content-Security-Policy the deployment sends:

- the product page, the login, and the 47 demo customers with the recommended walkthroughs picked from their scenario tags;
- a customer's bank with cards and movements;
- from a movement, «No reconozco este movimiento» opened the chat on that charge. The walk went on to:
  - the questions;
  - the confirmation with its expiry;
  - the case read back with its deadline: Ley 1755 for Colombia, and Ley 25.065 with the card block for Argentina.

  A charge already in a claim was not registered twice.
- the dispute tracker moved through the brief's states, and «Por qué» cited each rule with its source;
- the analyst console listed the queue and showed, for a case:
  - the rules that decided it, the policy version and the trace;
  - the bank's next legal deadline.

No page showed a console or Content-Security-Policy error, and no page scrolled sideways.

## An incident during the release, and its fix

Release #97 moved the case handoff to `handoff/2.1` and accepted only 2.1. The deployment's state keeps the handoffs written earlier as 2.0, so the analyst queue answered 503, and the end-to-end suite passed 6 of 12 against the URL.

The hotfix #98 reads both versions, with a regression test that stores a 2.0 handoff and lists it in the queue. It was deployed about fifteen minutes after the release; since then the queue answers 200 with the stored cases and the suite passes 12 of 12.

## Later releases

The same checks ran again after each release that followed: the continuous deployment, `/v1/health` reporting the new commit, and the end-to-end suite against the URL with the demo account.

| Release | `production` | What changed | End-to-end at the URL |
|---|---|---|---|
| #103 | `1de3691` | A purchase charged twice is registered as a duplicate for Complaints; prompt `interpreter-v6` | 12 of 12; a real A9 customer (AR-12) gets both purchases offered and the duplicate recognized |
| #107 | `dcf5c66` | The API adapter in layers, and the use cases on ports ([ADR 0008](adr/0008-the-api-adapter-in-layers.md)). The OpenAPI document is byte for byte the same | 12 of 12 |
| #110 | `e3cf46a` | The conversation flow in step modules ([ADR 0009](adr/0009-the-conversation-flow-in-step-modules.md)). On the development set, every reply, option, state and event is byte for byte the same | 12 of 12 |

## Not verified here

- **The audit of the running container** (`docker exec <api> env` and `docker history`) runs on the server, which only the team reaches over SSH. By construction, the CD writes six values to the server's `.env`, which only its owner can read:
  - the session secret;
  - the analyst key;
  - the hashes of the access accounts;
  - the language model's provider, key and workspace.

  The image is built in CI from this repository, which the publication audit checks.
