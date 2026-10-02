#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${HOME}/miniverse-control-plane/control_plane_v2"

systemctl --user is-enabled miniverse-worker.service
systemctl --user is-active miniverse-worker.service
cd "${APP_DIR}"
docker compose -f docker-compose.worker.yml ps
container_id="$(docker compose -f docker-compose.worker.yml ps -q worker)"
if [ -z "${container_id}" ]; then
  echo "worker container not found" >&2
  exit 1
fi
health="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${container_id}")"
echo "worker health=${health}"
if [ "${health}" != "healthy" ]; then
  docker logs --tail 100 "${container_id}" || true
  exit 1
fi
