# ADR 0001 · Single repository and hexagonal architecture

**Date:** 2026-10-03 · **Status:** accepted

## Context

The challenge asks for a public repository with the complete solution: agent, API, interface, data, learned component and evaluation. It also requires policy and permissions to be enforced outside the model's text, a comparable baseline, and a credible path to production. The team has a few days and a single person dedicated to the backend.

## Decision

1. **A single repository** containing the agent, API, web, pipeline, ML, evaluation, images and deployment.
2. **Hexagonal architecture:**
   - the domain (`vera/contracts`, `ports`, `core`, `policy`, `output`) depends only on the standard library, Pydantic and itself;
   - infrastructure (API, data, language model) enters through adapters that implement the ports;
   - an architecture test (`tests/architecture`) enforces the rule.
3. **A single process:** the agent runs as a library inside the API. There are no microservices.

## Rejected alternatives

| Alternative | Reason |
|---|---|
| Several repositories (agent, API, web) | More coordination and cross-version management; the challenge asks for one repository |
| Autonomous agent with unrestricted tools for the model | Policy must live outside the model; less predictable and harder to audit |
| Microservices | More parts that can fail on a small server, with no benefit at this scale |

## Consequences

- The language model, the database or the transaction source can change without touching the rules.
- The domain is tested without network or data; continuous integration uses mock adapters.
- Each port needs at least two adapters (the real one and the mock), and both pass the same contract tests.
