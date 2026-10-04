# Security

VERA is a hackathon demo for a synthetic bank. It holds no real customer, card or money, but it is built as if it did. This page states what it protects, how, and what remains open.

## Reporting a problem

Report it privately through this repository's GitHub security advisories (Security → Report a vulnerability). Do not open a public issue. Include what you did, what you expected and what happened; never include real personal data.

## What is protected, and how

| Threat | Control | Where |
|---|---|---|
| Acting on one customer's behalf with another's data | A demo session is a signed token for one customer, valid for 15 minutes; a document number never opens a session. Every tool sees only the session customer and the options offered to it; another customer's conversation or case answers exactly like one that does not exist | `api/security.py`, `vera/tools/toolbox.py`, property tests in `tests/properties` |
| An action the customer did not approve | Every write passes one action gate. It needs a confirmation token bound to the conversation, the customer, the tool and its exact arguments; the token is single-use and expires. The write is idempotent and read back. No tool moves or promises money (PROH-03) | `vera/tools/gate.py` |
| Prompt injection | Contained by design, not by instructions. The interpreter fills a closed schema and decides nothing. Gateway signals turn a flagged message into "not found" and a security event (POL-03), and flagged text never reaches the learned model | `vera/gateway/injection.py`, [ADR 0003](docs/adr/0003-prompt-injection-is-contained-by-design.md) |
| A reply that promises, blames or asks for secrets | Every reply passes an output validator. Links, requests for codes or passwords, promises of money, blame, claims to be human, and amounts that did not come from a tool are blocked before they reach the customer | `vera/output/validator.py` |
| Personal data in logs or in a model | Customer text is masked (cards, documents, emails, phones and names) before anything stores or interprets it. Operations logs hold no text, references, cards, amounts or merchants | `vera/gateway/masking.py`, `api/observability.py` |
| Abuse and runaway cost | 2,000 characters per message, 30 messages per minute per customer, and 40 turns per conversation; past the limit a person takes over | `vera/contracts/api.py`, `api/main.py`, `vera/core/flow.py` |
| Leaking internals | Unexpected errors answer 503 with a plain message; the trace stays in the log | `api/main.py` |
| Tampering with the record | Every turn is an event in a hash-chained, append-only log; the SQLite log refuses updates and deletes | `vera/core/events.py`, `vera/adapters/sqlite_event_log.py` |
| Dataset or secrets in the repository | No dataset record, database or model file is versioned. The publication check blocks data, secrets, forbidden files and large files in CI, and the demo subset is pseudonymized with a key that never leaves the building machine | `scripts/check_publication.py`, `pipeline/demo.py`, [datasheet](docs/datasheet.md) |
| Supply chain | Locked dependencies (`uv.lock`); no model file or pickle is shipped, because the classifier retrains from versioned phrases at start; images run as a non-root user on a read-only filesystem behind Caddy with HSTS and a strict CSP | `docker/`, `deploy/` |

## What remains open

- **The demo analyst view is open by default**, so reviewers can read handoffs. Setting `VERA_ANALYST_KEY` closes it ([deployment](docs/deployment.md)). A real deployment would need real analyst authentication.
- **Demo sessions are issued to anyone for any demo customer.** That is the point of a demo, and those customers are pseudonymized. A real deployment would authenticate customers with the bank's identity provider.
- **The injection signals are patterns.** A missed attack still meets the closed schema, the session isolation and the gate, so it cannot act; but it can make the conversation go down the wrong path.
- **The state lives in SQLite in one process.** Production at scale would use a database server, with the event log append-only by permissions ([operations](docs/operations.md)).
- **No penetration test or human red team has run yet;** the red team is part of the plan.
