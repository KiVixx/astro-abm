#!/usr/bin/env zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
PROJECT_ROOT="${SCRIPT_DIR:h:h}"
LOG_DIR="${PROJECT_ROOT}/logs/launchd"

mkdir -p "${LOG_DIR}"
exec >> "${LOG_DIR}/astro-abm-docker-start.log" 2>&1

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

echo "==== astro-abm docker startup $(date -u '+%Y-%m-%dT%H:%M:%SZ') ===="

if ! command -v docker >/dev/null 2>&1; then
  echo "docker CLI is not available on PATH=${PATH}"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker API is not ready; asking macOS to open OrbStack."
  open -gj -a OrbStack >/dev/null 2>&1 || open -gj /Applications/OrbStack.app >/dev/null 2>&1 || true
fi

for attempt in {1..60}; do
  if docker info >/dev/null 2>&1; then
    echo "Docker API ready after attempt ${attempt}."
    break
  fi
  sleep 3
done

if ! docker info >/dev/null 2>&1; then
  echo "Docker API still unavailable after waiting."
  exit 1
fi

docker compose -f "${PROJECT_ROOT}/docker-compose.questdb.yml" --profile maintenance up -d
docker compose -f "${PROJECT_ROOT}/docker-compose.questdb.yml" --profile maintenance ps

echo "Astro ABM Docker services are requested up."
