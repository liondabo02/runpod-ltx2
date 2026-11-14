#!/usr/bin/env bash
# AHOS Studio OS: reversible deployment of the private media queue on Oracle.
set -Eeuo pipefail

branch="feature/ahos-studio-worker-queue-20261114"
repository="https://github.com/liondabo02/runpod-ltx2.git"
target="/home/ubuntu/ahos-studio-media-worker"
state="/home/ubuntu/.local/share/ahos-studio-os"
unit="/etc/systemd/system/ahos-studio-os.service"

if [[ "$(id -un)" != "ubuntu" ]]; then
  echo "REFUSED: expected the existing ubuntu Oracle account"; exit 3
fi
if ! sudo -n true 2>/dev/null; then
  echo "REFUSED: authorized noninteractive sudo unavailable"; exit 3
fi
if [[ -e "$target" ]]; then
  echo "REFUSED: target already exists; never overwrite existing work"; exit 4
fi
if [[ ! -f "$unit" ]] || ! systemctl is-active --quiet ahos-studio-os.service; then
  echo "REFUSED: active previous Studio OS systemd unit required"; exit 5
fi
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8799/health >/dev/null
mkdir -p "$state/deploy-backups"
chmod 700 "$state/deploy-backups"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
unit_backup="$state/deploy-backups/ahos-studio-os-$stamp.service"
sudo -n cp "$unit" "$unit_backup"
sudo -n chown ubuntu:ubuntu "$unit_backup"
chmod 600 "$unit_backup"
echo "Original service file backed up."

export AHOS_MEDIA_STATE_DIR="$state" AHOS_MEDIA_BACKUP_NAME="before-media-$stamp.sqlite3"
python3 - <<'PY'
from pathlib import Path
import os,sqlite3
state=Path(os.environ["AHOS_MEDIA_STATE_DIR"])
source=state/"episodes.sqlite3"
backup_path=state/"deploy-backups"/os.environ["AHOS_MEDIA_BACKUP_NAME"]
if not source.is_file():
    raise SystemExit("REFUSED: existing episode database missing")
with sqlite3.connect(str(source)) as db, sqlite3.connect(str(backup_path)) as bak:
    db.backup(bak)
backup_path.chmod(0o600)
print("Existing episodes SQLite backup completed.")
PY

echo "Cloning only the dedicated new branch..."
git clone --quiet --depth 1 --single-branch --branch "$branch" "$repository" "$target"
python3 -m py_compile "$target/tools/studio_media_queue.py" "$target/tools/studio_oracle_service.py" "$target/tools/studio_media_worker_client.py" "$target/tools/ahos_studio_os.py"
echo "NEW_SHA=$(git -C "$target" rev-parse HEAD)"

rollback() {
  echo "ROLLBACK: restoring the previous service unit."
  sudo -n install -m 0644 "$unit_backup" "$unit"
  sudo -n systemctl daemon-reload
  sudo -n systemctl restart ahos-studio-os.service || true
}
trap rollback ERR

sudo -n install -m 0644 "$target/ops/oracle/ahos-studio-os.service" "$unit"
sudo -n systemctl daemon-reload
sudo -n systemctl restart ahos-studio-os.service
sleep 3
curl --fail --silent --show-error --max-time 8 http://127.0.0.1:8799/health
echo

python3 - <<'PY'
from pathlib import Path
import json,urllib.request
base="http://127.0.0.1:8799"
health=json.load(urllib.request.urlopen(base+"/health",timeout=8))
assert health["production_ready"] is False
token=(Path.home()/".local/share/ahos-studio-os/media-queue-admin.key").read_text().strip()
request=urllib.request.Request(base+"/api/media/status",
                               headers={"Authorization":"Bearer "+token})
with urllib.request.urlopen(request,timeout=8) as response:
    queue=json.load(response)
assert queue["schema"]=="ahos.media.queue-status.v1"
assert queue["production_ready"] is False
print("ORACLE_MEDIA_API_OK, workers=",len(queue["workers"]))
print("MEDIA_QUEUE_STATES=",queue["jobs"])
PY

trap - ERR
echo "ORACLE_MEDIA_QUEUE_DEPLOY_SUCCESS"
echo "No paid GPU resource or unverified production worker was started."
