#!/usr/bin/env bash
# Push churchagents images to Azure Container Registry.
#
# Default: tries `az acr build` (cloud build). Some subscriptions block ACR Tasks
# (TasksOperationsNotAllowed) — then we fall back to local `docker build` + `docker push`.
#
# Prerequisites: az login; ACR exists. For local fallback: Docker installed,
# `az acr login -n <acr>` (script runs this).
#
# Usage (from repo root):  bash terraform/build-and-push-acr.sh
# Force local Docker only: USE_LOCAL_DOCKER=1 bash terraform/build-and-push-acr.sh

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ACR="${ACR_NAME:-churchagentsacr}"
TAG="${IMAGE_TAG:-latest}"
SERVER="$(az acr show -n "${ACR}" --query loginServer -o tsv)"

echo "==> ACR: ${ACR} (${SERVER}), tag: ${TAG}"

az acr login -n "${ACR}"

docker_build_push() {
  local dockerfile=$1
  local context=$2
  local repo=$3
  local image="${SERVER}/${repo}:${TAG}"

  echo "    (docker) ${repo}"
  if docker buildx version >/dev/null 2>&1; then
    docker buildx build --platform linux/amd64 --push \
      -f "${dockerfile}" -t "${image}" "${context}"
  else
    docker build -f "${dockerfile}" -t "${image}" "${context}"
    docker push "${image}"
  fi
}

acr_cloud_build() {
  local dockerfile=$1
  local context=$2
  local repo=$3
  az acr build -r "${ACR}" \
    --file "${dockerfile}" \
    --image "${repo}:${TAG}" \
    "${context}"
}

# USE_LOCAL_DOCKER=1 skips ACR Tasks entirely (same as auto-fallback after TasksOperationsNotAllowed).
USE_LOCAL="${USE_LOCAL_DOCKER:-}"

if [[ "${USE_LOCAL}" != "1" ]]; then
  echo "==> Trying ACR cloud build (celery probe)..."
  if ! acr_cloud_build docker/Dockerfile . churchagents-celery 2>/tmp/acr_tasks_err; then
    if grep -q TasksOperationsNotAllowed /tmp/acr_tasks_err 2>/dev/null; then
      echo ""
      echo "Azure blocked ACR Tasks on this subscription (TasksOperationsNotAllowed)."
      echo "Falling back to local Docker build + push (linux/amd64)."
      echo ""
      USE_LOCAL=1
    else
      cat /tmp/acr_tasks_err
      exit 1
    fi
  fi
fi

if [[ "${USE_LOCAL}" == "1" ]]; then
  echo "==> celery worker"
  docker_build_push docker/Dockerfile . churchagents-celery
  echo "==> orchestrator"
  docker_build_push docker/Dockerfile.orchestrator . churchagents-orchestrator
  echo "==> dashboard"
  docker_build_push church-agents-dashboard/Dockerfile church-agents-dashboard churchagents-dashboard
else
  echo "==> orchestrator (cloud)"
  acr_cloud_build docker/Dockerfile.orchestrator . churchagents-orchestrator
  echo "==> dashboard (cloud)"
  acr_cloud_build church-agents-dashboard/Dockerfile church-agents-dashboard churchagents-dashboard
fi

echo ""
echo "Done. Repositories:"
az acr repository list -n "${ACR}" -o table || true
