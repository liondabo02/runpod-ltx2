#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/liondabo02/runpod-ltx2.git"
BRANCH="feature/agent-control-plane"
APP_DIR="${HOME}/miniverse-control-plane"
ENV_DIR="${HOME}/.config/miniverse"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
RUNTIME_DIR="${APP_DIR}/control_plane_v2/runtime"

mkdir -p "${ENV_DIR}" "${SYSTEMD_USER_DIR}"

if [ ! -d "${APP_DIR}/.git" ]; then
  git clone --branch "${BRANCH}" --single-branch "${REPO_URL}" "${APP_DIR}"
else
  git -C "${APP_DIR}" fetch origin "${BRANCH}"
  git -C "${APP_DIR}" checkout "${BRANCH}"
  git -C "${APP_DIR}" reset --hard "origin/${BRANCH}"
fi

mkdir -p "${RUNTIME_DIR}/state" "${RUNTIME_DIR}/workspaces"

if [ ! -f "${ENV_DIR}/runtime.env" ]; then
  cp "${APP_DIR}/control_plane_v2/.env.runtime.example" "${ENV_DIR}/runtime.env"
  chmod 600 "${ENV_DIR}/runtime.env"
  ln -sfn "${ENV_DIR}/runtime.env" "${APP_DIR}/control_plane_v2/.env.runtime"
  echo "Created ${ENV_DIR}/runtime.env. Fill model/API values before starting the service."
  exit 2
fi

ln -sfn "${ENV_DIR}/runtime.env" "${APP_DIR}/control_plane_v2/.env.runtime"

cp "${APP_DIR}/control_plane_v2/deploy/miniverse-worker.service" "${SYSTEMD_USER_DIR}/miniverse-worker.service"
systemctl --user daemon-reload
systemctl --user enable miniverse-worker.service
systemctl --user restart miniverse-worker.service
sleep 3
systemctl --user --no-pager --full status miniverse-worker.service || true

cd "${APP_DIR}/control_plane_v2"
docker compose -f docker-compose.worker.yml ps
