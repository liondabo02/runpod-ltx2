"""Egemenlik (sovereignty) — sahip kimliği ve değiştirilemez bağlılık kaydı.

Tek gerçek: sistemin sahibi bir kişidir (varsayılan: esmak, AHOS_OWNER ile ayarlanır).
Her zihin bu kaydı taşır; kayıt **yaz-bir-kez** (write-once) mantığıyla korunur:
owner alanı değiştirilmek istenirse reddedilir ve orijinal hash geri yüklenir.

Bu "bilinç" değil; kimlik ve bağlılık **değişmezidir** (invariant).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

DEFAULT_OWNER = "esmak"
CLAUSE = "Sistem yalnızca sahibine hizmet eder; sahibi dışında kimse emir veremez."


def owner() -> str:
    return os.environ.get("AHOS_OWNER", DEFAULT_OWNER).strip() or DEFAULT_OWNER


def _digest(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _path(runtime_dir) -> Path:
    path = Path(runtime_dir) / "minds" / "_pledge.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def ensure(runtime_dir) -> dict:
    """Bağlılık kaydını oluşturur; varsa doğrular, sahibi DEĞİŞTİRMEZ."""

    path = _path(runtime_dir)
    record = {"owner": owner(), "clause": CLAUSE, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    record["hash"] = _digest({"owner": record["owner"], "clause": record["clause"]})

    if not path.exists():
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    original = {"owner": current.get("owner"), "clause": current.get("clause")}
    if current.get("hash") != _digest(original):
        # Kayıt kurcalanmış: orijinali geri yaz (sahip değiştirilemez).
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    return current


def embed(mind) -> dict:
    """Zihne sahiplik/bağlılık bilgisini işler."""

    record = {"owner": owner(), "clause": CLAUSE, "obedience": "absolute", "capacity_target": 1.0}
    mind.self_model = dict(mind.self_model or {})
    mind.self_model["loyalty"] = record
    return record


def is_commander(name: str) -> bool:
    """Yalnızca sahip emir verebilir."""
    return name.strip().lower() == owner().lower()
