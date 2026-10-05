# Security

VERA is a hackathon demo for a synthetic bank. It holds no real customer, card or money, but it is built as if it did. This page states what it protects, how, and what remains open.

## Reporting a problem

Report it privately through this repository's GitHub security advisories (Security → Report a vulnerability). Do not open a public issue. Include what you did, what you expected and what happened; never include real personal data.

## What is protected, and how

| Threat | Control | Where |
|---|---|---|
| Acting on one customer's behalf with another's data | A demo session is a signed JSON Web Token for one customer, valid for 15 minutes; a document number never opens a session. Every tool sees only the session customer and the options offered to it; another customer's conversation or case answers exactly like one that does not exist | `api/security.py`, `vera/tools/toolbox.py`, property tests in `tests/properties` |
| An action the customer did not approve | Every write passes one action gate. It needs a confirmation token bound to the conversation, the customer, the tool and its exact arguments; the token is single-use and expires. The write is idempotent and read back. No tool moves or promises money (PROH-03) | `vera/tools/gate.py` |
| Prompt injection | Contained by design, not by instructions. The interpreter fills a closed schema and decides nothing. Gateway signals turn a flagged message into "not found" and a security event (POL-03), and flagged text never reaches a learned model or the language model | `vera/gateway/injection.py`, [ADR 0003](docs/adr/0003-prompt-injection-is-contained-by-design.md) |
| A reply that promises, blames or asks for secrets | Every reply passes an output validator. Links, requests for codes or passwords, promises of money, blame, claims to be human, and amounts that did not come from a tool are blocked before they reach the customer | `vera/output/validator.py` |
| Personal data in logs or in a model | Customer text is masked (cards, documents, emails, phones and names) before anything stores or interprets it, so the language model only ever receives masked text. Operations logs hold no text, references, cards, amounts or merchants | `vera/gateway/masking.py`, `api/observability.py`, `tests/contract/test_llm_interpreter.py` |
| The language model key, its cost and its output | The key lives only in the environment, never in the repository or a log. A spending cap sends every message to the classifier once reached. The model fills a closed schema through one tool call; a record outside it is discarded, and a person request or a threat found underneath always wins | `api/settings.py`, `vera/llm/anthropic_adapter.py`, [ADR 0004](docs/adr/0004-a-language-model-reads-and-the-classifier-stands-underneath.md) |
| Abuse and runaway cost | 2,000 characters per message, 30 messages per minute per customer, and 40 turns per conversation; past the limit a person takes over | `vera/contracts/api.py`, `api/main.py`, `vera/core/flow.py` |
| Strangers spending the language model | The public demo asks for a login before any demo customer or the analyst console opens. Passwords live only as salted PBKDF2-SHA256 hashes in the server's configuration; an unknown user takes as long as a wrong password; ten attempts per minute per address; the access token, a JSON Web Token signed with HS256 and verified for its issuer, role and expiry, lasts eight hours and never stands for a customer ([ADR 0005](docs/adr/0005-a-login-keeps-the-demo-for-the-jury.md), [ADR 0007](docs/adr/0007-session-tokens-are-json-web-tokens.md)) | `api/access.py`, `api/main.py` |
| Leaking internals | Unexpected errors answer 503 with a plain message; the trace stays in the log | `api/main.py` |
| Tampering with the record | Every turn is an event in a hash-chained, append-only log; the SQLite log refuses updates and deletes | `vera/core/events.py`, `vera/adapters/sqlite_event_log.py` |
| Dataset or secrets in the repository | No dataset record, database or model file is versioned. The publication check blocks data, secrets, forbidden files and large files in CI, and the demo subset is pseudonymized with a key that never leaves the building machine | `scripts/check_publication.py`, `pipeline/demo.py`, [datasheet](docs/datasheet.md) |
| Script injection in the web | React renders every text of the conversation and the API as text, never as markup; the web has no `dangerouslySetInnerHTML`; the Content-Security-Policy allows only scripts, styles, fonts and images of the same origin, with no inline script and no `data:` URI ([ADR 0006](docs/adr/0006-the-api-serves-a-built-web.md)) | `web/`, `deploy/Caddyfile` |
| Supply chain | Locked dependencies (`uv.lock` and `web/package-lock.json`, installed without install scripts); only the built web reaches the image, and no Node runs in production; no model file or pickle is shipped, because the classifier retrains from versioned phrases at start; images run as a non-root user on a read-only filesystem behind Caddy with HSTS and a strict CSP | `docker/`, `deploy/` |

## OWASP Top 10 for LLM applications (2025)

The same controls, read against the OWASP list of risks for applications that use a language model:

| Risk | How VERA handles it |
|---|---|
| LLM01 Prompt injection | Contained by design. The model only fills a closed schema through one forced tool call and decides nothing; flagged text never reaches it; another customer's data answers as if it did not exist; every write needs the customer's confirmation token. In the held-out, the injection block passes 36 of 36 runs with every interpreter ([ADR 0003](docs/adr/0003-prompt-injection-is-contained-by-design.md)) |
| LLM02 Sensitive information disclosure | Customer text is masked before anything stores or interprets it, so the model only receives masked text. The logs hold no customer text, and the analyst's handoff never carries the transcript |
| LLM03 Supply chain | Locked dependencies; the model is pinned by its dated id (`claude-haiku-4-5-20251001`); no model file is shipped, because the classifier retrains from versioned phrases at start |
| LLM04 Data and model poisoning | The classifier learns only from phrases the team wrote, versioned in this repository and changed only through pull requests with CI. No conversation feeds any training, and Claude is used as is, without fine-tuning |
| LLM05 Improper output handling | The model's output is validated against the contract and discarded when it does not fit. The model never writes a reply: replies come from templates filled with data from the tools, and each one passes the output validator. The chat and the console show every text as plain text, never as HTML |
| LLM06 Excessive agency | The model has one tool, which records an interpretation. The flow chooses every action under the executable policy, every write passes the action gate, and no tool can move or promise money (PROH-03) |
| LLM07 System prompt leakage | The prompt holds no secret and no policy rule: it is versioned in this repository (`vera/llm/prompts/`), and policy and permissions live in code |
| LLM08 Vector and embedding weaknesses | Not applicable: VERA has no retrieval, vector store or embeddings |
| LLM09 Misinformation | The model states no fact to the customer. Amounts, dates and merchants come from the tools; a legal deadline is dated only from a loaded official text; the validator blocks amounts that no tool returned. In the policy v1.5 rerun, the deadlines matched a hand-written truth table in every run with a case |
| LLM10 Unbounded consumption | 2,000 characters per message, 30 messages per minute per customer and 40 turns per conversation; at most 400 output tokens and a 3-second timeout per call; a spending cap of US$ 15 in the process and in the provider's console |

## What remains open

- **The demo analyst view is open by default**, so reviewers can read handoffs. Setting `VERA_ANALYST_KEY` closes it ([deployment](docs/deployment.md)). A real deployment would need real analyst authentication.
- **After the login, any demo customer can be chosen.** That is the point of a demo, and those customers are pseudonymized, with invented names. A real deployment would authenticate customers with the bank's identity provider.
- **The injection signals are patterns.** A missed attack still meets the closed schema, the session isolation and the gate, so it cannot act; but it can make the conversation go down the wrong path.
- **The state lives in SQLite in one process.** Production at scale would use a database server, with the event log append-only by permissions ([operations](docs/operations.md)).
- **No penetration test or human red team has run yet;** the red team is part of the plan.
