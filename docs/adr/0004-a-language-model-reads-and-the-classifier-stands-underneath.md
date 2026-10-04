# ADR 0004 · A language model reads, and the classifier stands underneath

**Date:** 2026-10-04 · **Status:** accepted; measured once the API key exists

## Context

The challenge asks for a language model and for its version and prompt to be documented. VERA already reads messages with two interpreters behind one port: keyword rules (the baseline) and a learned claim classifier (P42). The classifier only reads the opening claim; answers, choices and details in free text are still read by patterns, which miss many wordings. A language model reads any wording, in Spanish and Portuguese, but it can fail, be slow, cost money and be steered by the text it reads.

The team compared providers on 2026-10-03 (planning repository, `04_desarrollo/llm_proveedores_y_costos.md`). With about 3,000 calls the price does not decide: every option costs less than US$ 15. What decides is the data rule (only masked text leaves, and no tier that trains on it), valid output in the schema, p95 latency and how it reads to judges who weigh data governance.

## Decision

1. **Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) through the Anthropic SDK, behind the same interpreter port** (`vera/llm/anthropic_adapter.py`, `VERA_LLM=anthropic`). It is one provider for now; a second adapter before the first is measured would be a distraction. `LLM_MODEL` changes the model without touching the code.
2. **It reads, and never decides.**
   - One forced tool call whose input schema is the interpretation contract; a test keeps both equal.
   - A record that does not validate is discarded, never repaired.
   - The prompt is versioned (`vera/llm/prompts/interpreter-v1.md`), says that the message is data, and carries no secret.
3. **The classifier stands underneath, and the rules under it.**
   - Every message is read by the classifier interpreter first.
   - A person request or a threat it finds wins without asking the model (POL-01, POL-02).
   - Its safety words (threat, regulator, Pix, a question about VERA) are a floor that the model can only add to.
   - Text the gateway flagged as an injection never reaches the model.
4. **Every failure answers with the floor.** That covers a timeout (3 s, two retries in the SDK), an error, a record outside the schema and the spending cap. The service answers either way, as with the classifier (P54). Without a key, the rules answer and `/v1/health` says degraded.
5. **Only masked text, and the cost is measured.**
   - The API masks cards, documents, emails, phones and names before the flow, so the model never sees them; an API test checks it.
   - `/v1/metrics` reports calls, fallbacks, tokens and US$ spent against a cap (`LLM_MAX_SPEND_USD`, 15 by default). The cap lives in the process; the same cap is set in the provider's console, which survives restarts.

## Rejected alternatives

| Alternative | Reason |
|---|---|
| The model replaces the rules and the classifier | One outage, one timeout or one persuasive message would take the safety words with it; the plan asks for 100 % recall of person requests and threats, which the floor guarantees whatever the model reads |
| The model chooses the next step or the tool | The flow and the policy decide (ADR 0003); a model that decides is a model that can be talked into a refund |
| A cheaper provider first (Groq, OpenAI, Gemini, DeepSeek) | At this volume the difference is a few dollars. Free tiers that train on data are excluded. DeepSeek reads badly before judges who weigh data governance. An OpenAI-compatible adapter remains possible behind the same port |
| Structured output in strict mode | Not verified against the API yet; validation in code already discards anything outside the schema |

## Consequences

- With the model down, slow or out of budget, VERA keeps working at the level of the classifier, and the metrics show it.
- Each message read by the model costs about US$ 0.0025 and adds latency. Answers given with a button never call it.
- **Not measured yet.** The evaluation compares the rules and the classifier; the model enters the table, with its cost and p95 per case, once the key exists. Until then, its accuracy is a hypothesis, not a result.
- The tests use a fake client: no network, no key and no customer text leave the test run.
