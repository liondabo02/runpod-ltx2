"""Ters tünel bekçisi — model köprüsünün kendi kendini onarması.

Sorun: Oracle'daki Ollama'ya giden ters tünel (127.0.0.1:11500) düşünce model
çağrıları "tüm modeller başarısız" oluyor ve holding duruyor.

Çözüm: her turda sağlık kontrolü; tünel kapalıysa **ayrık (detached) ssh**
süreci başlatılır. Durum `runtime/tunnel.json`'a yazılır.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ENDPOINT = os.environ.get("AHOS_TUNNEL_ENDPOINT", "http://127.0.0.1:11500/v1/models")
HOST = os.environ.get("AHOS_TUNNEL_HOST", "ubuntu@130.61.35.81")
KEY = os.environ.get(
    "AHOS_TUNNEL_KEY", r"C:\Users\esmak\.ssh\ahos-quality-99\oracle_ed25519"
)
REMOTE_PORT = os.environ.get("AHOS_TUNNEL_REMOTE_PORT", "11500")


@dataclass(frozen=True)
class TunnelState:
    up: bool
    detail: str


def probe(timeout: float = 4.0) -> TunnelState:
    """Tünel ucundan model listesi alınabiliyor mu?"""

    try:
        with urllib.request.urlopen(ENDPOINT, timeout=timeout) as response:
            payload = json.loads(response.read().decode())
        models = [item.get("id") for item in payload.get("data", [])][:3]
        return TunnelState(True, "modeller: " + ", ".join(str(m) for m in models))
    except Exception as exc:  # noqa: BLE001 - kapalı say
        return TunnelState(False, f"kapalı ({type(exc).__name__})")


def _spawn() -> int:
    """Ayrık ssh süreci başlatır; pid döndürür."""

    command = [
        "ssh", "-N",
        "-o", "BatchMode=yes",
        "-o", "ServerAliveInterval=30",
        "-o", "ExitOnForwardFailure=yes",
        "-L", f"{REMOTE_PORT}:127.0.0.1:11434",
        "-i", KEY,
        "-o", "IdentitiesOnly=yes",
        HOST,
    ]
    creation = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation,
    )
    return process.pid


def ensure(runtime_dir: str | Path, *, wait_seconds: int = 12) -> dict:
    """Tüneli garanti eder: kapalıysa başlatır ve doğrular."""

    runtime = Path(runtime_dir)
    state = probe()
    record = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "before": {"up": state.up, "detail": state.detail},
        "started": False,
        "pid": None,
        "after": None,
    }

    if not state.up:
        try:
            record["pid"] = _spawn()
            record["started"] = True
        except Exception as exc:  # noqa: BLE001 - başlatma başarısız
            record["error"] = f"{type(exc).__name__}: {exc}"
        for _ in range(max(1, wait_seconds)):
            time.sleep(1)
            after = probe(timeout=2.0)
            if after.up:
                break
        record["after"] = {"up": after.up, "detail": after.detail}
    else:
        record["after"] = {"up": True, "detail": state.detail}

    path = runtime / "tunnel.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record
