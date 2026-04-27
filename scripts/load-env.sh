#!/usr/bin/env bash
# Load churchagents .env into the current shell (safe for quoted values and # in passwords).
# Usage:  source scripts/load-env.sh
#    or:  . scripts/load-env.sh
#
# Do NOT use: export $(cat .env | xargs)  — breaks quotes, spaces, and # characters.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}" >&2
  return 1 2>/dev/null || exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

echo "Loaded: ${ENV_FILE}"
echo "DJANGO_BASE_URL=${DJANGO_BASE_URL:-}"
echo "AGENT_JWT_EMAIL=${AGENT_JWT_EMAIL:-}"
if [[ -n "${AGENT_JWT_CHURCH_ID:-}" ]]; then
  echo "AGENT_JWT_CHURCH_ID is set (${#AGENT_JWT_CHURCH_ID} chars)"
else
  echo "AGENT_JWT_CHURCH_ID is unset (platform-wide tools)"
fi
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY is set (${#OPENAI_API_KEY} chars)"
else
  echo "OPENAI_API_KEY is unset"
fi
if [[ -n "${AGENT_JWT_PASSWORD:-}" ]]; then
  echo "AGENT_JWT_PASSWORD is set (${#AGENT_JWT_PASSWORD} chars)"
else
  echo "AGENT_JWT_PASSWORD is unset"
fi
