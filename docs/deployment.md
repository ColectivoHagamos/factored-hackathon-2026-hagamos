# Deployment

The public demo runs at **https://vera.colectivohagamos.com** on one small server: the API container (which also serves the web) behind Caddy, which obtains and renews the TLS certificate.

## How a deployment happens

1. A pull request from `qa` to `production` passes the full CI (lint, tests, publication check, image build and container health).
2. The push to `production` runs `.github/workflows/cd.yml`:
   - builds the image and pushes it to `ghcr.io/hagamoses/vera-api:<sha>`;
   - copies `deploy/docker-compose.prod.yml`, `deploy/Caddyfile` and `deploy/deploy.sh` to `/opt/vera`;
   - writes `/opt/vera/.env` from the repository secrets, sent over standard input with permissions 600;
   - runs `deploy.sh <sha>`, which pulls the image, starts the stack and waits for the container health check. If the check fails within two minutes, it restores the previous tag;
   - checks `https://vera.colectivohagamos.com/v1/health` from the outside.
3. Images are built only in GitHub Actions, never on the server.

**A shared server.** The demo runs on a server that also hosts other stacks, one of which owns port 80. VERA stays apart:
- Caddy publishes only 443 and obtains the certificate on that port (TLS-ALPN-01), so `http://` addresses never reach VERA; links are shared as `https://`.
- The compose project `vera` lives in `/opt/vera`, with memory limits of 300 MB for the API (measured: about 155 MB idle and 170 MB after ten conversations) and 64 MB for Caddy. Both carry `oom_score_adj: 500`, so that if the server runs out of memory, the kernel stops VERA first, never the stacks it shares the server with.
- The image is private: the job's short-lived token pulls it, with a Docker configuration of its own in `/opt/vera/.docker`.
- Nothing prunes images or volumes of the host, and `deploy.sh` touches only the `vera` project.

The CD rewrites `/opt/vera/.env` on every deployment, so a value added by hand on the server does not survive the next one: every setting lives in the repository secrets. Without the three language model secrets, VERA reads with the classifier; with them, Claude reads over the classifier ([ADR 0004](adr/0004-a-language-model-reads-and-the-classifier-stands-underneath.md)). The spending cap of the process is US$ 15, and the same cap is set in the provider's console.

Manual rollback, on the server: `cd /opt/vera && DOMAIN=vera.colectivohagamos.com ./deploy.sh "$(cat .previous_tag)"`.

## What lives where

| Item | Repository | Image | GitHub secrets | Server |
|---|---|---|---|---|
| Code, policy YAML, legal rules, templates, web | Yes | Yes | | |
| `demo.duckdb` (pseudonymized subset) | No | No | | `/opt/vera/data`, read-only |
| Cases and events (SQLite) | No | No | | Docker volume `vera_state` |
| Session secret, optional analyst key | No | No | Yes | `/opt/vera/.env` |
| Language model: `VERA_LLM=anthropic`, `LLM_API_KEY` and `LLM_WORKSPACE_ID` (optional) | No | No | Yes | `/opt/vera/.env` |
| Deployment SSH key | No | No | Yes | Public part in `authorized_keys` |
| HMAC key of the pseudonymization | No | No | No | No (only on the machine that builds the subset) |
| Dataset and cloud credentials of the organizers | No | No | No | No |

## One-time preparation of the server

| Step | Command or place |
|---|---|
| Dedicate the server to VERA; stop other stacks without deleting their volumes | `docker compose stop` in each project |
| Static public address | Elastic IP associated with the instance |
| Firewall | Inbound 80 and 443 from anywhere; 22 only for key-based SSH |
| Docker with the Compose plugin | `docker compose version` |
| Folders | `sudo mkdir -p /opt/vera/data && sudo chown "$USER" /opt/vera /opt/vera/data` |
| Demo subset, after its leak test | `scp demo.duckdb <user>@<host>:/opt/vera/data/demo.duckdb` |
| DNS | `A` record `vera` pointing to the Elastic IP in the DNS of `colectivohagamos.com` |
| Deployment key | A new key pair only for VERA: public part in `~/.ssh/authorized_keys` of the deployment user |
| Image visibility | After the first push, make the `vera-api` package public in GitHub so the server pulls without a token |

## Repository secrets

| Secret | Value |
|---|---|
| `DEPLOY_HOST` | Elastic IP of the server |
| `DEPLOY_USER` | Deployment user on the server |
| `DEPLOY_SSH_KEY` | Private part of the deployment key |
| `DEPLOY_KNOWN_HOSTS` | Output of `ssh-keyscan -t ed25519 <host>`, checked against the server fingerprint |
| `SESSION_SECRET` | Random value, for example `openssl rand -hex 32` |
| `VERA_ANALYST_KEY` | Optional. Empty keeps the demo analyst view open for reviewers; a value requires the `X-Analyst-Key` header |

## Checks after the first deployment

- `dig +short vera.colectivohagamos.com` returns the Elastic IP.
- `curl -I https://vera.colectivohagamos.com/v1/health` answers 200 with a valid certificate.
- `docker exec <api container> env` shows no cloud credentials, and `docker history` of the image shows no data copied.
