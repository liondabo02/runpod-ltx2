"""Yanlış rotalanmış plan görevlerini belge rotasına çevirir.

Sorun: `plan_to_missions` / `flush_plan_queue` plan adımlarını
"<departman> · <eylem> (işçi: <id>)" gibi KISA bir görev metniyle kuyruğa
yazıyor. Kısa metin "deterministic" sınıflanıyor, belge departmanında
proje kabul kapısı (tests/) olmadığı için görev `blocked` oluyor.

Bu araç yalnız bu şablonu taşıyan `pending`/`blocked` görevleri bulur ve
objective'i belge fabrikasının kabul kapısından geçecek biçime çevirir:

    Tasarım dokümanı üret: <departman> planı — <eylem>. İçerik: ...

Kullanım:
    python tools/repair_plan_missions.py           # kuru
    python tools/repair_plan_missions.py --apply
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "ahos_core" / "runtime" / "company-service.db"

# "creative · engelli listeyi cek (işçi: oyun-manager)"
_TEMPLATE = re.compile(r"^(?P<dept>[^\s·]+)\s*·\s*(?P<action>.+?)\s*\(işçi:\s*(?P<worker>[^)]*)\)\s*$")


def document_objective(department: str, action: str) -> str:
    return (
        f"Tasarım dokümanı üret: {department} planı — {action}. "
        "İçerik: amaç, kapsam, adım listesi, riskler."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--cancel-superseded", action="store_true",
        help="plan şablonu görevlerini 'planbind ile tekilleştirildi' diyerek kapat",
    )
    args = parser.parse_args(argv)

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = list(con.execute(
        "select mission_id, objective, status, primary_department from missions "
        "where status in ('pending','blocked') and mission_id like '%-plan-%'"
    ))

    if args.cancel_superseded:
        ids = [str(row["mission_id"]) for row in rows]
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        for mission_id in ids:
            con.execute(
                "update missions set status='cancelled', last_error=?, updated_at=? "
                "where mission_id=? and status in ('pending','blocked')",
                ("plan şablonu tekilleştirildi (planbind belge görevleri)", now, mission_id),
            )
        con.commit()
        # Bayat iş öğelerini arşive taşı (yeniden çalıştırma kirliliği bırakma).
        stale = ROOT / "ahos_core" / "runtime" / "tasks" / "_stale"
        stale.mkdir(parents=True, exist_ok=True)
        moved = 0
        for mission_id in ids:
            task_file = ROOT / "ahos_core" / "runtime" / "tasks" / f"{mission_id}.json"
            if task_file.is_file():
                task_file.replace(stale / task_file.name)
                moved += 1
        print(f"iptal edilen (tekilleştirilen) plan şablonu: {len(ids)} · taşınan bayat iş: {moved}")
        return 0

    targets = []
    for row in rows:
        match = _TEMPLATE.match(str(row["objective"] or "").strip())
        if not match:
            continue
        targets.append((row, match))

    print(f"şablon görev: {len(targets)} "
          f"(pending={sum(1 for r, _ in targets if r['status']=='pending')}, "
          f"blocked={sum(1 for r, _ in targets if r['status']=='blocked')})")
    if not args.apply:
        for row, match in targets[:5]:
            print(f"  {row['mission_id'][:44]:44} {row['status']:8} -> "
                  f"{document_objective(match['dept'], match['action'])[:70]}")
        print("kuru çalışma; yazmak için --apply")
        return 0

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    updated = 0
    for row, match in targets:
        objective = document_objective(match["dept"], match["action"])
        if row["status"] == "blocked":
            con.execute(
                "update missions set objective=?, status='pending', attempts=0, "
                "lease_owner=NULL, lease_until=NULL, next_attempt_at=0, "
                "last_error=?, result_json=NULL, updated_at=? where mission_id=?",
                (objective, "plan şablonu belge rotasına çevrildi", now, row["mission_id"]),
            )
        else:
            con.execute(
                "update missions set objective=?, updated_at=? where mission_id=?",
                (objective, now, row["mission_id"]),
            )
        updated += 1
    con.commit()
    print(f"güncellenen görev: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
