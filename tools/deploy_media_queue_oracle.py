"""Safe Windows launcher for existing Oracle Studio OS media queue deployment.

Never prints keys, tokens, the Oracle public IP or user prompts.
Requires the already-authorized private Oracle instance record and SSH.
No GPU allocation and no new spending. Run preflight before deploy.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

PREFLIGHT=r"""set -e
test "$(id -un)" = ubuntu
test -f /etc/systemd/system/ahos-studio-os.service
systemctl is-active ahos-studio-os.service
curl -fsS --max-time 5 http://127.0.0.1:8799/health
echo
if test -e /home/ubuntu/ahos-studio-media-worker; then
    echo "TARGET_EXISTS: deployment helper will refuse to overwrite it"
else
    echo "TARGET_FREE"
fi
test -f /home/ubuntu/.local/share/ahos-studio-os/episodes.sqlite3
sudo -n true
echo "ORACLE_PRECHECK_PASS"
"""

VERIFY=r"""set -e
systemctl is-active ahos-studio-os.service
python3 - <<'PY'
import json,sqlite3,urllib.request
from pathlib import Path
base="http://127.0.0.1:8799"
health=json.load(urllib.request.urlopen(base+"/health",timeout=8))
assert health["production_ready"] is False
secret=(Path.home()/".local/share/ahos-studio-os/media-queue-admin.key")
assert secret.is_file(), "Media queue has not been deployed"
request=urllib.request.Request(base+"/api/media/status",
                               headers={"Authorization":"Bearer "+secret.read_text().strip()})
with urllib.request.urlopen(request,timeout=8) as response:
    result=json.load(response)
assert result["schema"]=="ahos.media.queue-status.v1"
print("ORACLE_MEDIA_QUEUE",result["jobs"])
print("PROFESSIONAL_FILM_READY",result["production_ready"])
db=Path.home()/".local/share/ahos-studio-os/episodes.sqlite3"
with sqlite3.connect(str(db)) as con:
    print("PERSISTED_EPISODES",con.execute("SELECT COUNT(*) FROM episodes").fetchone()[0])
PY
"""


def connection_record(path: Path):
    info=json.loads(path.read_text(encoding="utf-8"))
    host=info.get("public_ip")
    user=info.get("ssh_user","ubuntu")
    # Only known literal host addresses, never command fragments from config.
    ipaddress.ip_address(host)
    if not isinstance(user,str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}",user):
        raise ValueError("Oracle SSH user identifier invalid")
    key=Path(info["ssh_key"]).expanduser().resolve()
    if not key.is_file():
        raise ValueError("Existing Oracle SSH key unavailable")
    return host,user,key


def run(mode: str, record: Path) -> int:
    host,user,key=connection_record(record)
    if mode=="deploy":
        script=ROOT/"ops/oracle/deploy-media-worker-queue.sh"
        if not script.is_file():
            raise ValueError("Version-controlled Oracle deployment script missing")
        data=script.read_bytes().replace(b"\r\n", b"\n")
    elif mode=="preflight":
        data=PREFLIGHT.encode("utf-8")
    elif mode=="verify":
        data=VERIFY.encode("utf-8")
    else:
        raise ValueError("Unknown action")
    cmd=["ssh","-o","BatchMode=yes","-o","StrictHostKeyChecking=yes",
         "-o","ConnectTimeout=10","-i",str(key),f"{user}@{host}","bash","-s"]
    # Remote script is from this checked-out repository, not Internet text.
    output=subprocess.run(cmd,input=data,capture_output=True,
                          timeout=200 if mode=="deploy" else 35,check=False)
    stdout=output.stdout.decode("utf-8",errors="replace")
    stderr=output.stderr.decode("utf-8",errors="replace")
    # Only fixed deployment/health summaries are emitted; avoid verbose SSH
    # command lines or private config values in the transcript.
    for line in stdout.splitlines():
        if ("ORACLE_" in line or "TARGET_" in line or "active"==line or
            "MEDIA_QUEUE" in line or "PERSISTED_EPISODES" in line or
            "PROFESSIONAL_FILM_READY" in line or "HEALTH=" in line):
            print(line[:600])
    if output.returncode:
        print("REMOTE_ACTION_FAILED",mode,"exit_code=",output.returncode)
        print("Remote stderr (redacted for secrets):",
              type(stderr).__name__,len(stderr),"bytes")
    else:
        print("REMOTE_ACTION_OK",mode)
    return output.returncode


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record",type=Path,required=True,
                        help="Existing private Oracle last-instance.json")
    parser.add_argument("--mode",choices=("preflight","deploy","verify"),required=True)
    args=parser.parse_args(argv)
    try:
        return run(args.mode,args.record)
    except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
        print("ACTION_BLOCKED",type(exc).__name__)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
