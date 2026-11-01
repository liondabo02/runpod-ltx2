"""İzole alt-ajan — Claude Code/SWE-agent `subagent` deseninin sadeleştirilmiş hâli.

Ana bağlamı kirletmeden bir araştırma/analiz yapar ve **yalnız özet** döndürür.
Varsayılan mod deterministiktir (model çağrısı yok): bilgi ağından ilgili
belgeleri, kuyruk durumunu ve depo haritasını toplar.

Kayıt: `runtime/subagents/<id>.json`
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SubagentRun:
    run_id: str
    task: str
    summary: str
    evidence: tuple[str, ...] = ()
    at: str = ""

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "task": self.task,
            "summary": self.summary,
            "evidence": list(self.evidence),
            "at": self.at,
        }


def _knowledge_hits(runtime: Path, query: str, limit: int = 4) -> list[str]:
    try:
        from . import knowledge

        hits = knowledge.search(runtime, query, limit=limit)
        return [str(hit.get("path") or hit.get("source") or "") for hit in hits if hit]
    except Exception:  # noqa: BLE001 - bilgi ağı isteğe bağlı
        return []


def _queue_snapshot(runtime: Path) -> str:
    import sqlite3

    db = runtime / "company-service.db"
    if not db.exists():
        return "kuyruk yok"
    try:
        with sqlite3.connect(db) as con:
            counts = dict(con.execute("select status, count(*) from missions group by status").fetchall())
        return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    except sqlite3.Error:
        return "kuyruk okunamadı"


def run(runtime_dir: str | Path, task: str, *, project_root: str | Path | None = None) -> SubagentRun:
    """İzole bağlamda görevi analiz eder; yalnız özeti döndürür."""

    runtime = Path(runtime_dir)
    evidence: list[str] = []

    docs = _knowledge_hits(runtime, task)
    evidence.extend(docs)
    queue_text = _queue_snapshot(runtime)

    repo_lines: list[str] = []
    if project_root:
        try:
            from .repo_map import repo_map_text

            repo_lines = repo_map_text(project_root, task, limit=5).splitlines()[1:]
            evidence.extend(repo_lines[:5])
        except Exception:  # noqa: BLE001 - harita isteğe bağlı
            pass

    parts = [f"Görev: {task}"]
    if docs:
        parts.append("İlgili belgeler: " + ", ".join(docs[:4]))
    if repo_lines:
        parts.append("İlgili dosyalar: " + "; ".join(line.strip("- ") for line in repo_lines[:4]))
    parts.append("Kuyruk: " + queue_text)

    stamp = int(time.time())
    sub = SubagentRun(
        run_id=f"SUB-{stamp}",
        task=task,
        summary="\n".join(parts),
        evidence=tuple(evidence[:8]),
        at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )

    directory = runtime / "subagents"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{sub.run_id}.json").write_text(
        json.dumps(sub.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return sub
