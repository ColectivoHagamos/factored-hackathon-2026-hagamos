# Operations

How to see what VERA is doing, follow one conversation end to end, notice when something goes wrong, and what happens when a part fails. Deployment and rollback are in [deployment.md](deployment.md).

## Logs

The API writes one JSON object per line to standard output (`api/observability.py`), which the container runtime collects.

| Event | When | Fields |
|---|---|---|
| `request` | Every HTTP request | `request_id`, `method`, `route` (the template, such as `/v1/conversations/{conversation_id}/messages`, never the ids), `status`, `ms` |
| `turn` | Every customer message | `trace_id`, `request_id`, `ms`, `rules` (policy rules applied), `tools` (tool and result, such as `search_charges:ok`), `tool_failures`, `handoff` (queue), `security_event`, `fraud_alert`, `validator_blocked` |
| `interpreter_fallback` | At start, when the configured interpreter cannot start | `configured`, `using`, `error` (the exception type only) |

**What the logs never hold:** the customer's text, a customer reference, a card, an amount or a merchant. Only rule ids, tool names, statuses, timings and random ids are written.

Every response carries `X-Request-ID`. A caller can send its own id, and it is kept when it is a plain token of 8 to 64 characters.

## Following one conversation

The trace id of a conversation is `trace-<conversation_id>`. It appears in every `turn` line and in the analyst's handoff (`trace_id`). To follow a conversation end to end:

1. Take the trace id from the handoff in the analyst console, or the conversation id from the request path.
2. Filter the log lines by it: every turn, with its rules, tools and transfer.
3. For the full record, read the conversation's events. Each turn is a chain of events linked by hash (customer message, interpretation, rule decisions, tool calls and results, confirmation, read-back, reply), and the chain can be verified and replayed (`vera/core/events.py`).

## Metrics

`GET /v1/metrics` requires the analyst role. It returns counters since the process started and recent latencies:

- `requests`, and responses by class: `responses_2xx`, `responses_4xx`, `responses_5xx`;
- `turns`, `handoffs_fraud`, `handoffs_complaints`, `security_events`, `fraud_alerts`, `tool_failures` and `validator_blocks`;
- `request_ms` and `turn_ms`: p50 and p95 over the last 2,000 values;
- `interpreter` and `degraded`.

Spending is not tracked, because no paid model is called (the cost per case is US$ 0); the counter arrives with a language model adapter.

## Alerts

These thresholds are defined for whoever watches the metrics; the demo has no paging system.

| Signal | Alert when | First action |
|---|---|---|
| `responses_5xx` | More than 1 % of requests in 5 minutes | Read the logs around the time; roll back if a deploy just happened |
| `tool_failures` | More than 5 % of turns in 5 minutes | Check the volume with the demo subset and the state; the conversations are already going to a person (POL-13) |
| `security_events` | More than 10 in 5 minutes, or from one customer | Look for an attack pattern; the rate limit already caps one customer at 30 messages per minute |
| `validator_blocks` | Any | A reply was blocked before it reached a customer: read its turn and fix the template or the flow |
| `turn_ms` p95 | Above 1,000 ms | Check the server load; see the load test below |
| `degraded` in `/v1/health` | True | The classifier did not start and the rules are answering; read the `interpreter_fallback` line |

## When a part fails

| Failure | What VERA does |
|---|---|
| The learned classifier cannot start | The rules interpreter answers; `/v1/health` reports `degraded` and the interpreter in use |
| A bank read fails or times out | It is tried once more; then the conversation goes to a person and nothing is filled in (POL-13) |
| A write fails | The write is not retried, because its confirmation token was spent; the read-back does not match, so the conversation goes to a person |
| Any other error in a request | 503 with a plain message (`provider_unavailable`); the trace stays in the log, never in the response |
| Too many messages from one customer | 429 (`VERA_MESSAGES_PER_MINUTE`, default 30) |
| A conversation that does not converge | After 40 customer turns nothing more is interpreted, and a person takes over |

## Load test

`scripts/load_test.py` runs concurrent conversations against a running VERA, each one up to the registration of a case, and measures every request. It must run against a local server with a raised rate limit, never against the public demo.

| Configuration (one process, one laptop) | Conversations · workers | Requests | p50 | p95 | Errors |
|---|---|---:|---:|---:|---:|
| Mock data, in-memory state, classifier | 60 · 12 | 492 | 21 ms | 34 ms | 0 |
| Demo subset (DuckDB), SQLite state and event log on disk, classifier: the production setup | 60 · 12 | 450 | 86–89 ms | 265–332 ms | 0 |

The first run found a real defect. The API serves requests from several threads, and the state used one SQLite connection without a lock on its reads, so concurrent requests failed with a 503. Two registrations at the same time could also compute the same case id. The state, both event logs and the DuckDB adapter are now safe across threads, and `tests/unit/test_concurrency.py` reproduces both failures.

## Limits

- **One process with a SQLite state.** Writes are serialized, which is enough for a demo but not for a bank. Production at scale would put the state in a database server, with the event log append-only by permissions.
- **Metrics live in memory and restart with the process.** A real deployment would export them to a time-series store and page on the alerts above.
