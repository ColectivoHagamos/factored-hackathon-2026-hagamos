# ADR 0008 · The API adapter in layers

**Date:** 2026-10-05 · **Status:** accepted

## Context

The HTTP API grew from four endpoints to fifteen, all defined inside one `create_app()` function of 373 lines, with the rate limiter, the error answers and the use cases mixed into it. The bodies that only HTTP knows (login, sessions, profile, movements, queue, health, errors) shared a module of the domain with the conversation's contract that the core returns. The hexagonal boundary held (ADR 0001), but the driving adapter itself had no structure.

## Decision

1. **The API is a driving adapter in layers, and dependencies point inward:**

   ```
   routers (controllers) ──► services (use cases) ──► vera core, policy, tools ──► ports ◄── adapters
          │                          │
       guards (sessions)       schemas (HTTP bodies)
   ```

   - `api/routers/`: one router per area (access, operations, demo, conversations, customer, analyst, pages). A handler checks who calls through a guard, hands the request to one use case and returns its body.
   - `api/services/`: the use cases, free of the web framework (`AccessService`, `DemoDirectory`, `CustomerViews`, `ConversationService`, `AnalystDesk`). They work on the container's ports and raise `ApiFailure` with a closed set of codes.
   - `api/guards.py`: the customer, analyst and access sessions, each a dependency that turns a JSON Web Token into a session or answers 401.
   - `api/schemas.py`: the bodies only HTTP knows. The conversation's contract stays in `vera/contracts/conversation.py`, because the core produces it, and the API publishes it unchanged.
   - `api/context.py`: one `AppContext` per application (settings, container, metrics and use cases), reached through FastAPI's dependency injection, never through module globals.
   - `api/app.py`: the factory (middleware, error answers, routers and the built web). `api/main.py` is only the process entry point.
2. **A port for the analyst's reads.** `AnalystQueuePort` (`vera/ports/bank.py`): the queue, and each handoff or transfer by its reference. The desk depends on the port, not on the SQLite adapter.
3. **The layering is a test.** `tests/architecture/test_dependency_rule.py` fails the CI when:
   - the domain imports infrastructure;
   - a use case imports the web framework;
   - a router imports an adapter, a store, a language model or the composition root.

## Rejected alternatives

| Alternative | Reason |
|---|---|
| Keep every endpoint in one function | Each change touched the whole API; use cases could only be tested through HTTP |
| A separate reply model for HTTP, mapped from the core's | Two identical models and a mapping, with no reader that needs them apart |
| A dependency injection framework | FastAPI's `Depends` and one context per application already give constructor injection and test doubles |

## Consequences

- The OpenAPI document is the same: the same 14 paths in the same order, with the same operations, parameters and responses. The only change is the description of `LoginRequest`.
- Each use case can be tested without HTTP, and a new channel would reuse the services with its own controllers.
- The conversation's state machine is still one module (`vera/core/flow.py`). Splitting it into one handler per step is the next refactoring, measured with the full suite and the evaluation sets.
