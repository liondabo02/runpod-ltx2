"""Eski engelli görevleri kurtar ya da kapat.

Karar kuralı:
- Görev metninde **projede var olan** bir dosya adı geçiyorsa → kurtarılabilir:
  durum `pending`'e alınır, adım kilidi (taskboard) temizlenir, yeniden denenir.
- Geçmiyorsa → **iptal** edilir ("belirsiz görev; yeni sistemle yeniden tanımlanmalı").

Böylece kuyruk temizlenir ve yalnız yeni/güncel sistemin işleyebileceği iş kalır.
"""

from __future__ import annotations

import io
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

from ahos.owner_console import build_default_console
from ahos.targets import missing_targets, mentioned_files

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
APPLY = "--apply" in sys.argv

console = build_default_console(R)
con = sqlite3.connect(R / "company-service.db")
con.row_factory = sqlite3.Row

rows = list(con.execute(
    "select mission_id, objective, primary_department from missions where status='blocked'"
))
print(f"engelli: {len(rows)} · mod: {'UYGULA' if APPLY else 'deneme (dry-run)'}\n")

rescued: list[str] = []
cancelled: list[str] = []
for row in rows:
    mission_id = row["mission_id"]
    objective = row["objective"] or ""
    department = row["primary_department"] or ""
    project = console._project_for_department(department) if department else None
    reason = ""
    if project is None:
        reason = "departman/proje yok"
    else:
        root = project.work_path or project.path
        files = mentioned_files(objective)
        if not files:
            reason = "somut dosya hedefi yok"
        else:
            missing = missing_targets(root, objective)
            if missing and len(missing) == len(files):
                reason = "hedef dosyaların hiçbiri projede yok"
    if reason:
        cancelled.append(mission_id)
        if APPLY:
            con.execute(
                "update missions set status='cancelled', last_error=?, updated_at=datetime('now') "
                "where mission_id=?",
                (f"kapatıldı: {reason}", mission_id),
            )
    else:
        rescued.append(mission_id)
        if APPLY:
            con.execute(
                "update missions set status='pending', attempts=0, max_attempts=2, "
                "lease_owner=NULL, lease_until=NULL, next_attempt_at=0, result_json=NULL, "
                "last_error='kurtarma: güncel sistemle yeniden deneme', updated_at=datetime('now') "
                "where mission_id=?",
                (mission_id,),
            )

if APPLY:
    con.commit()
    # taskboard'daki eski "done" kayıtlarını temizle
    board_path = R / "taskboard.json"
    if board_path.exists() and rescued:
        payload = json.loads(board_path.read_text(encoding="utf-8"))
        tasks = payload.get("tasks") if isinstance(payload, dict) else payload
        keep = [t for t in tasks if not any(str(t.get("task_id", "")).startswith(m) for m in rescued)]
        if isinstance(payload, dict):
            payload["tasks"] = keep
            board_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            board_path.write_text(json.dumps(keep, ensure_ascii=False, indent=2), encoding="utf-8")
        print("taskboard temizlendi:", len(tasks) - len(keep))

print(f"kurtarılan: {len(rescued)} · kapatılan: {len(cancelled)}")
print("kapatma örnekleri:")
for mission in cancelled[:5]:
    print("  ", mission[:60])
print("kurtarma örnekleri:")
for mission in rescued[:5]:
    print("  ", mission[:60])
if APPLY:
    print("kuyruk:", dict(con.execute("select status,count(*) from missions group by status").fetchall()))
