"""Yedek + geri yükleme tatbikatı: kopya al, bütünlüğü doğrula, geri yükle.

Adımlar:
1. Canlı veritabanının tutarlı kopyası (sqlite backup API).
2. Kopyada `PRAGMA integrity_check` + `PRAGMA foreign_key_check`.
3. Kopyayı ayrı bir runtime dizinine "geri yükle" ve görev sayılarını karşılaştır.
4. Kanıtı `quality/evidence/` altına yaz.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

ROOT = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2")
DB = ROOT / "ahos_core" / "runtime" / "company-service.db"
BACKUPS = ROOT / "ahos_core" / "runtime" / "backups"
EVIDENCE = ROOT / "quality" / "evidence"


def _counts(path: Path) -> dict:
    con = sqlite3.connect(path)
    try:
        rows = con.execute("SELECT status, COUNT(*) FROM missions GROUP BY status").fetchall()
        total = con.execute("SELECT COUNT(*) FROM missions").fetchone()[0]
    finally:
        con.close()
    return {"total": total, "by_status": {status: count for status, count in rows}}


def main() -> int:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    BACKUPS.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    backup = BACKUPS / f"company-service-{stamp}.db"

    source = sqlite3.connect(DB)
    target = sqlite3.connect(backup)
    with target:
        source.backup(target)
    source.close()
    target.close()

    con = sqlite3.connect(backup)
    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    foreign = con.execute("PRAGMA foreign_key_check").fetchall()
    con.close()

    with tempfile.TemporaryDirectory() as tmp:
        restored = Path(tmp) / "company-service.db"
        shutil.copy2(backup, restored)
        restored_counts = _counts(restored)

    live_counts = _counts(DB)
    evidence = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "backup": str(backup),
        "backup_bytes": backup.stat().st_size,
        "integrity_check": integrity,
        "foreign_key_violations": len(foreign),
        "live": live_counts,
        "restored": restored_counts,
        "restore_matches": live_counts == restored_counts,
        "ok": integrity == "ok" and not foreign and live_counts == restored_counts,
    }
    path = EVIDENCE / f"backup-restore-{stamp}.json"
    path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")

    # yalnızca son 5 yedeği tut
    for old in sorted(BACKUPS.glob("company-service-*.db"))[:-5]:
        old.unlink(missing_ok=True)

    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0 if evidence["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
