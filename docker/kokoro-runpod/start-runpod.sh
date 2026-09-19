#!/bin/sh
set -eu

export PORT="${PORT:-8880}"
export PORT_HEALTH="${PORT_HEALTH:-8888}"
export KOKORO_PORT="${KOKORO_PORT:-$PORT}"

python3 /opt/runpod/health_bridge.py &
HEALTH_BRIDGE_PID=$!

cleanup() {
  kill "$HEALTH_BRIDGE_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

exec /opt/src/run.sh
