#!/usr/bin/env bash
# Build the iotawatt-sync image on this host and push it to GitHub Container Registry.
#
# One-time setup (needs a GitHub PAT with write:packages scope):
#   echo "$GHCR_TOKEN" | docker login ghcr.io -u danielgoepp --password-stdin
#
# Usage:
#   ./build-and-push.sh            # build + push :latest and :<git-sha>
#   NO_PUSH=1 ./build-and-push.sh  # build only
#   ALLOW_DIRTY=1 ./build-and-push.sh  # push even with uncommitted changes
set -euo pipefail

IMAGE="${IMAGE:-ghcr.io/danielgoepp/iotawatt-sync}"
cd "$(dirname "$0")"

SHA="$(git rev-parse --short HEAD)"
if [[ -n "$(git status --porcelain)" ]]; then
  SHA="${SHA}-dirty"
  if [[ -z "${NO_PUSH:-}" && -z "${ALLOW_DIRTY:-}" ]]; then
    echo "Working tree has uncommitted changes; refusing to push :latest." >&2
    echo "Commit first, or use NO_PUSH=1 (build only) or ALLOW_DIRTY=1 (push anyway)." >&2
    exit 1
  fi
fi

docker build \
  --label "org.opencontainers.image.revision=$(git rev-parse HEAD)" \
  --label "org.opencontainers.image.created=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -t "${IMAGE}:latest" \
  -t "${IMAGE}:${SHA}" \
  .

if [[ -n "${NO_PUSH:-}" ]]; then
  echo "Built ${IMAGE}:latest and ${IMAGE}:${SHA} (not pushed)"
  exit 0
fi

docker push "${IMAGE}:${SHA}"
docker push "${IMAGE}:latest"
echo "Pushed ${IMAGE}:latest and ${IMAGE}:${SHA}"
