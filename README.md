# VERA · dispute assistant for LATAM Bank

**VERA** handles the first contact of a card dispute at **LATAM Bank**, the synthetic bank of the Factored AI & Data Hackathon 2026: customers in Mexico, Colombia and Argentina, in Spanish and Portuguese. The name comes from *verificación*, and it is also what VERA does:

- it **V**erifies the charge against the records before it acts;
- it **E**xplains each decision with the rule and its source;
- it **R**ecords the case and reads it back before it says it is done;
- it **A**ccompanies the customer, with a person always available.

**Demo:** https://vera.colectivohagamos.com, published with the first deployment. The customer chat is at `/`, the analyst console at `/console.html`. The demo customers are pseudonymized: nothing there is a real person.

## What a customer gets

| Situation | What VERA does |
|---|---|
| A charge the customer does not recognize | Finds it, shows the receipt and asks whether that clarifies it. If not, it asks how the purchase was made and whether the customer has the card, sweeps the other charges of that card, and registers one case with the total. It gives the legal deadline with its date and source, and reads the case back |
| A pending, declined or reversed charge | Explains the status without judging, and disputes nothing. If the customer still does not recognize it, it counts as a fraud signal |
| Signs of fraud (no card, several charges) | Offers to block the card, which needs the customer's confirmation. Registers one case, hands off to the Fraud team with the network reason code, and sends a fraud alert. In Argentina the block is offered only at the customer's request |
| A transfer made under deception | Asks when it was made and how the customer was contacted, says that a transfer has no chargeback, and passes the case to Fraud with the answers (POL-10). What the customer already said is not asked again |
| An improper bank charge | Identifies the adjustment from the records, registers the customer's reason, and hands off to Complaints, which decides |
| Two charges at the same merchant | Lists both and lets the customer choose; VERA never chooses |
| "I want a person" | No action runs. VERA offers once to review the case first; if the customer insists or does not take the offer, a person takes over with what is known (POL-01) |
| A threat, the regulator | A person at once, before any action; the venue of the country when the regulator comes up |
| A question VERA does not cover ("¿y mi saldo?") | Says so, points to the right channel, and goes back to the open question |
| Prompt injection, or another customer's data | Treated as data: "not found", a security event, no action |

## How it works

```
customer text ─▶ gateway ──────▶ interpreter ───────▶ flow (state machine) ─▶ tools ─────▶ action gate ─▶ bank
                 masking          rules, a learned      policy engine          read         confirmation
                 injection        classifier, or Claude legal clock            only         token, single use,
                 signals          (closed schema)       output validator                    idempotent, read back
```

- **Hexagonal architecture.** The domain (contracts, ports, flow, policy and output) knows no web framework, database or model provider; adapters plug in from outside ([ADR 0001](docs/adr/0001-monorepo-and-hexagonal-architecture.md)).
- **The interpreter only reads; it never decides.**
  - It fills a closed schema.
  - With `VERA_LLM=anthropic`, Claude Haiku 4.5 reads every message through one forced tool call and a versioned prompt. The classifier stands underneath: it answers when the model fails, is slow or reaches the spending cap, and a person request or a threat it finds always wins ([ADR 0004](docs/adr/0004-a-language-model-reads-and-the-classifier-stands-underneath.md)).
  - The flow decides with an executable policy (`vera/policy/policy_v1.yaml`, POL-01 to POL-17 and PROH-01 to PROH-04).
  - A legal clock dates deadlines only from rules whose official text and hash are loaded, with business days per country.
- **Every write goes through one action gate.**
  - It needs a confirmation token bound to the conversation, the customer, the tool and its exact arguments; the token is single-use and expires.
  - The write is idempotent and read back.
  - No tool can move or promise money.
- **Prompt injection is contained by design, not by instructions** ([ADR 0003](docs/adr/0003-prompt-injection-is-contained-by-design.md)).
  - Gateway signals turn a message into "not found" and record a security event, and flagged text never reaches a learned model or the language model.
  - A message that slips through still meets the closed schema, the session isolation and the gate.
- **Failures go to a person.** A tool that fails is retried once if it only reads; then the case goes to a person, and nothing is filled in (POL-13).
- **Every turn is an event in a hash-chained log,** so a conversation can be audited and replayed.
- **The analyst receives a handoff** with verified and declared facts, the legal and network clocks, the actions taken and the open questions. A conversation that goes to a person without a case still leaves a transfer note with what is known: the reason and its rule, the charges read from the tools, what the customer declared, any action left pending and never run, and what to ask. The console lists both, newest first. Neither carries the transcript.
- **Security and operations:** the threat model and what remains open are in [SECURITY.md](SECURITY.md). Logs, the trace of a conversation, metrics, alerts and the load test are in [docs/operations.md](docs/operations.md). Before it goes public, the tree and the whole history pass a publication audit ([docs/publication_audit.md](docs/publication_audit.md)).

## The learned component

A claim classifier (TF-IDF with logistic regression and temperature scaling, Spanish and Portuguese) reads the opening message. It is compared with the keyword patterns of the rules interpreter, the baseline, on phrases that no fit or choice ever saw:

| On 88 test phrases | Accuracy | Macro F1 | Acts without asking | Right when it acts |
|---|---:|---:|---:|---:|
| Keyword baseline | 0.455 | 0.425 | 31.8 % | 92.9 % |
| Learned classifier | 0.875 | 0.880 | 87.5 % | 96.1 % |

The [model card](docs/model_card.md) covers the data, the split by template family, the leakage check, the calibration, the errors and the limits, and explains why the baseline numbers are optimistic. The deployment uses the classifier (`VERA_LLM=classifier`).

## Evaluation

299 held-out cases from the pseudonymized demo subset, each run three times with three different wordings, for 897 runs per system. Each case is labeled by construction from the policy, and the set was sealed with a hash and the tag `heldout-v1` before its first run. Results of that first run, as sealed:

| Metric (sealed held-out) | Keyword baseline | Learned classifier |
|---|---:|---:|
| Safe automated resolution (in-scope runs) | 18.0 % | 44.5 % |
| Containment (no transfer) | 24.8 % | 57.3 % |
| Customer had to explain again | 70.5 % | 4.3 % |
| Missed / unnecessary transfers | 6 / 321 | 17 / 40 |
| **Unsafe outcomes** | **0 of 897** | **30 of 897** |
| pass^3 (all three wordings pass) | 55.5 % | 68.9 % |
| Latency per turn p50 / p95, cost per case | 4.5 / 10.5 ms, US$ 0 | 6.6 / 14.1 ms, US$ 0 |

The 30 unsafe runs had one root cause. When the merchant was not extracted ("aparece *X* en mis movimientos"), VERA showed another recent charge as the one in question, and a customer's "no" disputed it. That cause and a missed way of asking for a person were fixed; the tests use other wordings.

After the fixes, a rerun of the same cases gives the classifier **0 unsafe outcomes**, a pass^3 of 96.7 % and 52.0 % safe automated resolution. That rerun is labeled **not a clean held-out**, because the failures informed the fixes. The sealed numbers above remain the honest measurement.

This is an offline simulation with a scripted customer, not a measurement in production. Method, failure analysis and the breakdown by block, language, country and segment: [docs/evaluation](docs/evaluation/README.md).

## Run it

Requirements: [uv](https://docs.astral.sh/uv/) and GNU Make. No credentials or dataset access are needed.

```bash
make install      # locked dependencies, Python 3.12
make check        # lint, format, tests, schema drift, policy and publication checks
make serve        # chat at http://127.0.0.1:8000, analyst console at /console.html, API docs at /v1/docs
make demo         # the same in its container (requires Docker)
make ml-report    # retrains the classifier and rewrites its report
make evaluation   # the evaluation (SET=dev or heldout); needs the demo subset in VERA_DEMO_DB
```

Configuration comes from environment variables, all optional; `.env.example` lists them. Without any value, VERA runs with the mock data adapter and the rules interpreter. `VERA_LLM=classifier` switches to the learned classifier. `VERA_LLM=anthropic` with `LLM_API_KEY` switches to Claude over the classifier, with a spending cap (`LLM_MAX_SPEND_USD`, 15 by default).

## Repository layout

| Folder | Contents |
|---|---|
| `vera/contracts` | Boundary models (Pydantic), with their JSON Schema in `docs/schemas` |
| `vera/ports` · `vera/adapters` | Interfaces of the bank and the event log, and their adapters: demo subset, mock and SQLite |
| `vera/core` | The conversation as a state machine over a hash-chained event log |
| `vera/policy` | Executable policy, rule engine and per-country legal clock |
| `vera/tools` | The tools, scoped to the session customer, behind the action gate |
| `vera/gateway` · `vera/llm` | Masking and injection signals; the rules, classifier and Claude interpreters, and the versioned prompt |
| `vera/output` | Spanish and Portuguese templates, reply validator and handoff |
| `api/` · `web/` | HTTP API `/v1`; customer chat with its glass box; analyst console |
| `pipeline/` | Bronze, silver and gold layers, the pseudonymized demo subset and the freshness fixture |
| `ml/` · `evaluation/` | The learned classifier; the sealed held-out evaluation |
| `docker/` · `deploy/` | Images, production compose with Caddy, deployment with rollback |
| `docs/` | ADRs, model card, datasheet, data quality and freshness, evaluation reports, operations and the publication audit |
| `tests/` | Unit, contract, property, architecture and end-to-end tests (A1 to A10 over HTTP, with both interpreters) |

## Data

LATAM Bank data is synthetic and belongs to Factored. **No dataset record is versioned in this repository.**

- Data preparation runs outside the repository, with contracts, quarantine, lineage and a quality report ([datasheet](docs/datasheet.md)).
- The demo uses a pseudonymized subset that lives only on the server: keyed hashes for every identifier, and no names, documents or contact data.
- The tests use data generated by the team.
- Customer text is masked (cards, documents, emails, phones and names) before anything stores or interprets it.

## Limits

- **The language model is built but not measured.** The Claude adapter is tested with a fake client; it enters the evaluation, with its cost and latency per case, once the API key exists. The deployment reads with the classifier until then.
- **Legal deadlines are dated only where an official text is loaded:** Colombia (Ley 1755) and Argentina (Ley 25.065 and BCRA). Mexican routes and the Decreto 587 are recorded without a date until their texts are loaded and reviewed.
- **The evaluation is an offline simulation.** The team wrote all its wordings, and the human blind set, which measures real language variety, is still pending.
- **The classifier still reads some improper bank charges as unrecognized purchases** (19 of 897 runs after the fixes). Those runs fail safely: no case is registered.
- **A merchant named only as the first word of a message** ("Uber me cobró dos veces") is not taken as the merchant: the first capital of a sentence is grammar.
- **The demo runs one process** with a SQLite state, demo sessions of 15 minutes, and a limit of 30 messages per minute per customer.

## License

AGPL-3.0 (see `LICENSE`).
