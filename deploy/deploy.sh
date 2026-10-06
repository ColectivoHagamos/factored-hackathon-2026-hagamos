#!/usr/bin/env bash
# Deploy one image tag of VERA on the server, wait for the API health check and roll back if it fails.
#
# Usage (on the server, from /opt/vera): ./deploy.sh <image_tag>
# Needs DOMAIN in the environment, .env with the secrets and data/demo.duckdb in place.
# Exit codes: 0 deployed · 1 health check failed and the previous tag was restored · 2 wrong usage.
set -euo pipefail

tag="${1:-}"
[ -n "$tag" ] || { echo "usage: ./deploy.sh <image_tag>"; exit 2; }
cd "$(dirname "$0")"
[ -f .env ] && [ -f data/demo.duckdb ] || { echo "missing .env or data/demo.duckdb"; exit 2; }

compose() { VERA_IMAGE_TAG="$1" docker compose -f docker-compose.prod.yml "${@:2}"; }

healthy() {
  local container status
  for _ in $(seq 1 60); do
    container=$(compose "$1" ps -q api)
    status=$(docker inspect -f '{{.State.Health.Status}}' "$container" 2>/dev/null || echo starting)
    [ "$status" = "healthy" ] && return 0
    sleep 2
  done
  return 1
}

previous=$(cat .current_tag 2>/dev/null || true)
# The repository moved to the ColectivoHagamos organization, and its image with it. The running image takes the new
# name too, so a rollback finds it on the server without the registry.
if [ -n "$previous" ] && docker image inspect "ghcr.io/hagamoses/vera-api:$previous" >/dev/null 2>&1; then
  docker tag "ghcr.io/hagamoses/vera-api:$previous" "ghcr.io/colectivohagamos/vera-api:$previous"
fi
compose "$tag" pull api
compose "$tag" up -d --remove-orphans

if healthy "$tag"; then
  [ -n "$previous" ] && echo "$previous" > .previous_tag
  echo "$tag" > .current_tag
  echo "deployed $tag"
  exit 0
fi

echo "health check failed for $tag"
compose "$tag" logs --tail 50 api || true
if [ -n "$previous" ]; then
  compose "$previous" up -d --remove-orphans
  echo "rolled back to $previous"
fi
exit 1
