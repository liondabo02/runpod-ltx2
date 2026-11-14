"""Open the Oracle-hosted Studio OS over SSH without exposing a public port.

The actual Studio OS runs 24/7 on Oracle independently of this launcher.
This script is only a local browser access tunnel and will exit on Ctrl+C.
"""
from __future__ import annotations
import json
from pathlib import Path
import socket
import subprocess
import time
import webbrowser

ROOT=Path(__file__).resolve().parents[1]
RECORD=ROOT/"ops/oracle/last-instance.json"
LOCAL_PORT=8800
REMOTE_PORT=8799


def main():
    if not RECORD.is_file():
        raise SystemExit("Oracle connection record missing (local private file)")
    conf=json.loads(RECORD.read_text(encoding="utf-8"))
    key=Path(conf["ssh_key"]).expanduser()
    if not key.is_file():
        raise SystemExit("Oracle SSH key is missing")
    argv=[
        "ssh", "-N", "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=yes",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "ConnectTimeout=10",
        "-i", str(key), "-L",
        f"127.0.0.1:{LOCAL_PORT}:127.0.0.1:{REMOTE_PORT}",
        f"{conf.get('ssh_user','ubuntu')}@{conf['public_ip']}",
    ]
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1",LOCAL_PORT)) == 0:
            print(f"Local port {LOCAL_PORT} is already in use; do not hijack.")
            raise SystemExit(2)
    process=subprocess.Popen(argv, stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        for _ in range(60):
            if process.poll() is not None:
                detail=process.stderr.read().decode("utf-8",errors="replace")[-350:]
                raise RuntimeError("SSH tunnel failed: "+detail)
            with socket.socket() as probe:
                probe.settimeout(0.2)
                if probe.connect_ex(("127.0.0.1",LOCAL_PORT)) == 0:
                    break
            time.sleep(0.2)
        else:
            raise RuntimeError("SSH tunnel could not bind to localhost")
        url=f"http://127.0.0.1:{LOCAL_PORT}/"
        print("AHOS Studio OS cloud browser:",url)
        webbrowser.open(url)
        print("Oracle remains available if this computer shuts down. Ctrl+C closes browser tunnel only.")
        process.wait()
    finally:
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill()


if __name__=="__main__":
    main()
