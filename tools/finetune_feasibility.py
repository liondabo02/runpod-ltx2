"""G018 — Güvenli deneysel model geliştirme FİZİBİLİTE raporu.

Bu araç model eğitmez. Yalnız mevcut doğrulanmış veriyi, sınıf dengesini,
donanım varlığını ve lisans/maliyet gereksinimlerini analiz eder; LoRA/fine-tuning
için uygulanabilirlik kararı ve gerekli onayları listeler.

Kural: gerçek ağırlık eğitilmediyse "model kendini eğitti" denmez.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "ahos_core" / "runtime"
DB = RUNTIME / "company-service.db"
REPORT = RUNTIME / "reports" / "finetune-feasibility.json"
DOC = ROOT / "docs" / "FINETUNE-FIZIBILITE.md"


def _missions() -> list[dict]:
    if not DB.is_file():
        return []
    with sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True) as con:
        rows = con.execute(
            "select mission_id, objective, status, result_json from missions "
            "where result_json is not null").fetchall()
    out = []
    for mission_id, objective, status, raw in rows:
        try:
            payload = json.loads(raw)
        except TypeError:
            continue
        if not (payload.get("delivery") or {}).get("verified"):
            continue
        out.append({"mission_id": mission_id, "objective": str(objective or ""),
                    "status": str(status)})
    return out


def _gpu() -> str:
    if not shutil.which("nvidia-smi"):
        return "no nvidia-smi"
    try:
        proc = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total",
                               "--format=csv,noheader"], capture_output=True,
                              text=True, timeout=15)
        return (proc.stdout or proc.stderr).strip()[:200] or "unknown"
    except Exception as exc:  # noqa: BLE001
        return f"error: {type(exc).__name__}"


def build() -> dict:
    missions = _missions()
    duplicates = 0
    seen = set()
    for mission in missions:
        digest = hashlib.sha256(mission["objective"].encode("utf-8")).hexdigest()
        if digest in seen:
            duplicates += 1
        seen.add(digest)
    labels = Counter(mission["status"] for mission in missions)
    completed = labels.get("completed", 0)
    other = len(missions) - completed
    split_ok = completed >= 50 and other >= 20
    gpu = _gpu()
    feasible = bool(split_ok and gpu != "no nvidia-smi")
    reasons = []
    if not split_ok:
        reasons.append(f"train/test split için yeterli ve dengeli örnek yok "
                       f"(completed={completed}, other={other})")
    if gpu == "no nvidia-smi":
        reasons.append("yerel GPU bulunamadı; bulut GPU ücretli ve Harun onayı gerekir")
    reasons.append("lisans ve model ağırlığı koşulları doğrulanmadı")
    result = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "schema": "ahos.finetune-feasibility.v1",
        "verified_missions": len(missions),
        "labels": dict(labels),
        "duplicate_objectives": duplicates,
        "train_test_split_possible": split_ok,
        "gpu": gpu,
        "training_performed": False,
        "feasible_now": feasible,
        "reasons": reasons,
        "approvals_required": ["ücretli GPU bütçesi (Harun)", "model lisansı",
                               "üretim modeli değişikliği (bağımsız benchmark sonrası)"],
        "recommended_alternative": "politika düzeyinde A/B (tools/eval_learning.py); "
                                   "ağırlık değişikliği yok",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    DOC.write_text(
        "# G018 — Deneysel Model Geliştirme Fizibilitesi\n\n"
        f"- Üretim: {result['at']}\n"
        f"- Doğrulanmış görev: **{len(missions)}** · tamamlanan: **{completed}** · diğer: **{other}**\n"
        f"- Tekrarlı hedef: **{duplicates}**\n"
        f"- GPU: `{gpu}`\n"
        f"- Eğitim yapıldı mı: **hayır**\n"
        f"- Şimdi uygulanabilir mi: **{'evet' if feasible else 'hayır'}**\n\n"
        "## Gerekçeler\n"
        + "".join(f"- {reason}\n" for reason in reasons)
        + "\n## Gerekli onaylar\n"
        + "".join(f"- {item}\n" for item in result["approvals_required"])
        + "\n##Öneri\n"
        f"- {result['recommended_alternative']}\n",
        encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
