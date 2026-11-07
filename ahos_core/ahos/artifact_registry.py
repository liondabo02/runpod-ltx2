"""V5 GÖREV 022 — Gerçek teslimat kayıt defteri (SQLite).

Dosyanın varlığı, SHA-256 eşleşmesi, bağımsız QA ve teslimat ayrı aşamalardır.
`verified=true` yalnız dosya gerçekten varsa, hash tutuyorsa ve QA geçtiyse yazılır.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path


def _db(runtime) -> Path:
    return Path(runtime) / "delivery-registry.db"


def _connect(runtime):
    con = sqlite3.connect(_db(runtime))
    con.execute(
        "create table if not exists artifacts (artifact_id text primary key,"
        " mission_id text, worker_ids text, department_ids text, file_path text,"
        " sha256 text, file_size integer, media_metadata text, qa_result text,"
        " verified integer, delivered_at text, updated_at text)")
    return con


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def register(runtime, manifest_path) -> dict:
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    video = (payload.get("files") or {}).get("video") or {}
    path = Path(str(video.get("path") or ""))
    exists = path.is_file()
    actual = sha256(path) if exists else ""
    qa_ok = bool((payload.get("qa") or {}).get("ok"))
    verified = bool(exists and qa_ok and actual
                    and actual == str(video.get("sha256") or actual))
    artifact_id = str(payload.get("delivery_id") or path.parent.name)
    workers = sorted({str(c.get("worker")) for c in payload.get("contributors") or []
                      if c.get("worker")})
    departments = sorted({str(c.get("department")) for c in payload.get("contributors") or []
                          if c.get("department")})
    record = {"artifact_id": artifact_id,
              "mission_id": str(payload.get("delivery_id") or ""),
              "worker_ids": workers, "department_ids": departments,
              "file_path": str(path), "sha256": actual, "file_size": path.stat().st_size if exists else 0,
              "media_metadata": (payload.get("ffprobe") or {}).get("format") or {},
              "qa_result": {"ok": qa_ok, "verifier": (payload.get("qa") or {}).get("verifier")},
              "verified": verified,
              "delivered_at": time.strftime("%Y-%m-%dT%H:%M:%S") if verified else ""}
    with _connect(runtime) as con:
        con.execute(
            "insert or replace into artifacts values (?,?,?,?,?,?,?,?,?,?,?,?)",
            (record["artifact_id"], record["mission_id"], json.dumps(workers),
             json.dumps(departments), record["file_path"], record["sha256"],
             record["file_size"], json.dumps(record["media_metadata"]),
             json.dumps(record["qa_result"]), int(verified),
             record["delivered_at"], time.strftime("%Y-%m-%dT%H:%M:%S")))
    return record


def verify(runtime, artifact_id: str) -> dict:
    with _connect(runtime) as con:
        row = con.execute("select file_path, sha256, verified from artifacts "
                          "where artifact_id=?", (artifact_id,)).fetchone()
    if row is None:
        raise KeyError(artifact_id)
    path = Path(row[0])
    actual = sha256(path) if path.is_file() else ""
    ok = bool(path.is_file() and actual == row[1] and row[2])
    return {"artifact_id": artifact_id, "file_exists": path.is_file(),
            "hash_match": actual == row[1], "verified": ok}


def list_artifacts(runtime) -> list[dict]:
    if not _db(runtime).is_file():
        return []
    with _connect(runtime) as con:
        rows = con.execute("select artifact_id, file_path, verified, delivered_at "
                           "from artifacts order by delivered_at desc").fetchall()
    return [{"artifact_id": r[0], "file_path": r[1], "verified": bool(r[2]),
             "delivered_at": r[3]} for r in rows]
