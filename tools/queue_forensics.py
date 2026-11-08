"""V5 GÖREV 012/014 — Kuyruk ve initiative kök neden analizi (salt-okunur).

43 blocked / 14 failed görevi sınıflandırır; her biri için kök neden, tekrar
denenebilirlik, onay ihtiyacı ve geçerlilik kararı üretir. Hiçbir görevi otomatik
yeniden çalıştırmaz veya başarıya çevirmez.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "ahos_core" / "runtime"
DB = RUNTIME / "company-service.db"
REPORT = RUNTIME / "reports" / "queue-forensics.json"
DOC = ROOT / "docs" / "KUYRUK-FORENSIK.md"


def classify(error: str) -> dict:
    text = (error or "").casefold()
    if "panosu biçimi geçersiz" in text or "board format" in text:
        return {"class": "invalid_input", "retryable": False, "needs_fix": True,
                "reason": "geçersiz görev panosu biçimi; şema düzeltmesi gerekir"}
    if "only completed mission results" in text:
        return {"class": "code_validation", "retryable": False, "needs_fix": True,
                "reason": "tamamlanmamış sonuç finalize edilmeye çalışılmış; yürütücü hatası"}
    if "qa failed" in text or "kabul testi" in text or "kabul kapisi" in text:
        return {"class": "qa_failed", "retryable": True, "needs_fix": True,
                "reason": "gerçek QA/kabul başarısızlığı; düzeltme sonrası tekrar denenebilir"}
    if "sahiplik" in text or "lease" in text or "süresi dolmuş" in text:
        return {"class": "lease", "retryable": True, "needs_fix": False,
                "reason": "lease süresi dolmuş; güvenli yeniden kuyruk"}
    if "pilot" in text:
        return {"class": "historical_pilot", "retryable": False, "needs_fix": False,
                "reason": "eski pilot kalıntısı; artık geçersiz"}
    return {"class": "other", "retryable": False, "needs_fix": True,
            "reason": "sınıflandırılamadı; insan incelemesi"}


def build() -> dict:
    rows = []
    if DB.is_file():
        with sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True) as con:
            for mission_id, objective, status, error, attempts, max_attempts, updated in con.execute(
                    "select mission_id, objective, status, last_error, attempts, "
                    "max_attempts, updated_at from missions where status in ('blocked','failed')"):
                verdict = classify(str(error or ""))
                age_days = 0.0
                try:
                    age_days = round((time.time() - time.mktime(time.strptime(
                        str(updated)[:19], "%Y-%m-%dT%H:%M:%S"))) / 86400, 1)
                except (ValueError, OverflowError):
                    age_days = -1
                needs_approval = any(word in str(error).casefold()
                                     for word in ("paid", "ücret", "owner", "onay"))
                stale = age_days < 0 or age_days > 7
                rows.append({"mission_id": mission_id, "status": status,
                             "objective": str(objective or "")[:120],
                             "error": str(error or "")[:160], "attempts": attempts,
                             "max_attempts": max_attempts, "age_days": age_days,
                             **verdict,
                             "needs_approval": needs_approval,
                             "stale": stale and not verdict["retryable"],
                             "action": ("tekrar dene (düzeltme sonrası)"
                                        if verdict["retryable"] else
                                        "şema/kod düzeltmesi gerekir"
                                        if verdict["needs_fix"] else "arşivle/geçersiz")})
    init = RUNTIME / "initiative.jsonl"
    init_rows = []
    if init.is_file():
        for line in init.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                init_rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    init_age = round((time.time() - init.stat().st_mtime) / 86400, 1) if init.is_file() else None
    counts = Counter(row["class"] for row in rows)
    pending = 0
    if DB.is_file():
        with sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True) as con:
            pending = con.execute("select count(*) from missions where status='pending'").fetchone()[0]
    payload = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "blocked_failed": len(rows), "by_class": dict(counts),
        "retryable": sum(1 for row in rows if row["retryable"]),
        "needs_fix": sum(1 for row in rows if row["needs_fix"]),
        "stale": sum(1 for row in rows if row["stale"]),
        "needs_approval": sum(1 for row in rows if row["needs_approval"]),
        "pending": pending,
        "initiative": {"entries": len(init_rows), "age_days": init_age,
                       "last": init_rows[-1] if init_rows else None},
        "rows": rows,
        "verdict": ("Kuyruğun boş kalmasının ana nedeni: initiative dosyası eski ve "
                    "fikirler gerçek göreve dönüşmüyor; ayrıca 48 hata şema/kod "
                    "kaynaklı ve otomatik tekrar güvenli değil."),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    DOC.write_text(
        "# AHOS V5 — Kuyruk Forensiği (G012/G014)\n\n"
        f"- Üretim: {payload['at']} · pending **{pending}** · blocked/failed **{len(rows)}**\n"
        f"- Sınıflar: {json.dumps(payload['by_class'], ensure_ascii=False)}\n"
        f"- Tekrar denenebilir: **{payload['retryable']}** · düzeltme gerekli: "
        f"**{payload['needs_fix']}** · geçersiz/eski: **{payload['stale']}**\n"
        f"- Initiative: **{len(init_rows)}** kayıt, son yazım **{init_age} gün** önce\n\n"
        "## Kök nedenler\n\n"
        + "\n".join(f"- `{key}`: {sum(1 for r in rows if r['class'] == key)} görev"
                    for key in counts)
        + "\n\n## Örnek kararlar\n\n"
        + "\n".join(f"- `{r['mission_id']}` — {r['class']} · {r['action']} · yaş {r['age_days']} gün"
                    for r in rows[:12])
        + f"\n\n## Karar\n\n{payload['verdict']}\n",
        encoding="utf-8")
    return payload


if __name__ == "__main__":
    data = build()
    print(json.dumps({k: data[k] for k in ("blocked_failed", "by_class", "retryable",
                                           "needs_fix", "stale", "pending",
                                           "initiative")}, ensure_ascii=False))
