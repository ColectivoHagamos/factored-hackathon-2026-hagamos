# ADR 0002 · The API serves the web

**Date:** 2026-10-03 · **Status:** accepted

## Context

The demo has two pages, the customer chat and the analyst console. Both are static files that call `/v1`. The challenge asks for a deployment that a reviewer can open without setup, on a small server.

## Decision

1. The FastAPI application serves `web/` at `/` and the API at `/v1`, from the same image and process.
2. Caddy stays in front only to terminate TLS with automatic certificates; it adds no routing logic.
3. The pages are plain HTML, CSS and JavaScript, with no build step and no external scripts or fonts.

## Rejected alternatives

| Alternative | Reason |
|---|---|
| A separate web container behind Caddy | A second image to build, version and deploy, for files that never change at run time |
| A single-page framework with a build step | More tooling and a supply-chain surface, with no benefit for two pages |
| Scripts or fonts from a CDN | An external dependency at run time and a privacy leak to a third party |

## Consequences

- One URL, one image and one health check cover the whole demo.
- Text that comes from the conversation or from the API is rendered with `textContent`, so it never becomes markup; only validated identifiers (case ids and option numbers) are interpolated into HTML.
