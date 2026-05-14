#!/usr/bin/env zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
PROJECT_ROOT="${SCRIPT_DIR:h:h}"
LABEL="com.kivixx.astro-abm-docker"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"
RUNTIME_DIR="${HOME}/Library/Application Support/AstroABM"
START_SCRIPT="${RUNTIME_DIR}/start_astro_abm_docker.sh"
LOG_DIR="${HOME}/Library/Logs/AstroABM"
USER_DOMAIN="gui/$(id -u)"

mkdir -p "${HOME}/Library/LaunchAgents" "${RUNTIME_DIR}" "${LOG_DIR}"

cat > "${START_SCRIPT}" <<SCRIPT
#!/usr/bin/env zsh
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT}"
LOG_DIR="${LOG_DIR}"

mkdir -p "\${LOG_DIR}"
exec >> "\${LOG_DIR}/astro-abm-docker-start.log" 2>&1

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

echo "==== astro-abm docker startup \$(date -u '+%Y-%m-%dT%H:%M:%SZ') ===="

if ! command -v docker >/dev/null 2>&1; then
  echo "docker CLI is not available on PATH=\${PATH}"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker API is not ready; asking macOS to open OrbStack."
  open -ga OrbStack >/dev/null 2>&1 || open /Applications/OrbStack.app >/dev/null 2>&1 || true
fi

for attempt in {1..60}; do
  if docker info >/dev/null 2>&1; then
    echo "Docker API ready after attempt \${attempt}."
    break
  fi
  sleep 3
done

if ! docker info >/dev/null 2>&1; then
  echo "Docker API still unavailable after waiting."
  exit 1
fi

if docker container inspect abm-questdb >/dev/null 2>&1 && docker container inspect abm-maintenance >/dev/null 2>&1; then
  docker start abm-questdb abm-maintenance >/dev/null
else
  if [[ ! -r "\${PROJECT_ROOT}/docker-compose.questdb.yml" ]]; then
    echo "Existing containers are missing and compose file is not readable from launchd: \${PROJECT_ROOT}/docker-compose.questdb.yml"
    exit 1
  fi
  docker compose -f "\${PROJECT_ROOT}/docker-compose.questdb.yml" --profile maintenance up -d
fi

docker ps --filter "name=abm-" --format "{{.Names}} {{.Status}} {{.Ports}}"
echo "Astro ABM Docker services are requested up."
SCRIPT

chmod +x "${START_SCRIPT}"

cat > "${PLIST_PATH}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>${START_SCRIPT}</string>
  </array>

  <key>RunAtLoad</key>
  <true/>

  <key>StartInterval</key>
  <integer>300</integer>

  <key>WorkingDirectory</key>
  <string>${RUNTIME_DIR}</string>

  <key>StandardOutPath</key>
  <string>${LOG_DIR}/launchd.out.log</string>

  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/launchd.err.log</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
</dict>
</plist>
PLIST

plutil -lint "${PLIST_PATH}"

launchctl bootout "${USER_DOMAIN}" "${PLIST_PATH}" >/dev/null 2>&1 || true
launchctl bootstrap "${USER_DOMAIN}" "${PLIST_PATH}"
launchctl enable "${USER_DOMAIN}/${LABEL}"
launchctl kickstart -k "${USER_DOMAIN}/${LABEL}"

echo "Installed ${LABEL}"
echo "Plist: ${PLIST_PATH}"
echo "Logs: ${LOG_DIR}"
