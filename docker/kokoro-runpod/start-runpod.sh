#!/bin/sh
set -eu

export PORT="${PORT:-8880}"
export PORT_HEALTH="${PORT_HEALTH:-8888}"
export KOKORO_PORT="${KOKORO_PORT:-$PORT}"

# RunPod Load Balancer already authenticates the public request with the
# RunPod API key. Its gateway does not pass that Authorization header
# through to the application container, so Kokoro's optional second
# Bearer layer must be explicitly disabled behind this trusted gateway.
# Setting the variable (even empty) also prevents Kokoro from auto-
# generating a private key on a persistent /var/lib/kokoro volume.
export KOKORO_API_KEY=""

python3 /opt/runpod/health_bridge.py &
HEALTH_BRIDGE_PID=$!

cleanup() {
  kill "$HEALTH_BRIDGE_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

exec /opt/src/run.sh
