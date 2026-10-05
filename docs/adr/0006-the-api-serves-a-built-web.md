# ADR 0006 · The API serves a built web

**Date:** 2026-10-05 · **Status:** accepted · **Supersedes:** decision 3 of [ADR 0002](0002-api-serves-the-web.md)

## Context

The two pages of the first demo (customer chat and analyst console) became a product web: a page for the bank that evaluates VERA, a login, the demo customers, each customer's bank with cards and movements, the chat with its dispute tracker and glass box, and the analyst console. The interface follows the brand brief (palette, Manrope, iconography and the five dispute states) in Spanish, English and Portuguese. Hand-written HTML and JavaScript no longer keep that consistent.

## Decision

1. The web is a single-page application in `web/`: React 19, TypeScript, Tailwind CSS 4 and TanStack Router, built by Vite into `web/dist`.
2. The image builds it in a Node stage, from `package-lock.json` and without install scripts (`npm ci --ignore-scripts`); only the static files reach the final image. No Node runs in production.
3. The API still serves the web from the same origin (`api/web.py`): a path that names no file answers with `index.html`, so the browser router picks the page; a missing file and anything under `/v1` stay a 404; hashed assets are cached for a year and the index page is revalidated.
4. The Content-Security-Policy stays `default-src 'self'`: no inline scripts, no `data:` URIs (`assetsInlineLimit: 0`), the Manrope files are bundled, and nothing loads from a third party.
5. The web always calls the real API; it has no simulated data of its own. Development runs the API with the mock bank adapter and `npm run dev`, which forwards `/v1` to it.

## Rejected alternatives

| Alternative | Reason |
|---|---|
| Keep plain HTML and JavaScript | Six screens, three languages and a design system drift apart without components and types |
| Server-side rendering | A Node process in production for pages that need no server data before the login |
| A separate web container | A second image and deployment for static files the API already serves from the same origin |
| Fonts or scripts from a CDN | A runtime dependency and a privacy leak to a third party, and the policy would have to allow it |

## Consequences

- CI adds a web job (lint, unit tests, type check and build), and the image build fails if the web does not compile.
- `/console.html` redirects to `/analista`, so old links still work.
- The supply chain of the web is the npm lockfile: dependencies are few (React, the router, lucide icons, Manrope and Tailwind) and install scripts never run.
