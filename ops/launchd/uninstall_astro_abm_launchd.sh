#!/usr/bin/env zsh
set -euo pipefail

LABEL="com.kivixx.astro-abm-docker"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"
RUNTIME_SCRIPT="${HOME}/Library/Application Support/AstroABM/start_astro_abm_docker.sh"
USER_DOMAIN="gui/$(id -u)"

launchctl bootout "${USER_DOMAIN}" "${PLIST_PATH}" >/dev/null 2>&1 || true
rm -f "${PLIST_PATH}"
rm -f "${RUNTIME_SCRIPT}"

echo "Uninstalled ${LABEL}"
