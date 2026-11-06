"""İki öğrenme yöntemini AYRI değerlendirme kümesinde karşılaştırır.

Yöntem A (history_rate): geçmiş başarı oranı yüksek plan tipini seçer.
Yöntem B (evidence_grounded): görev metnindeki deterministik desen + doğrulanmış
kanıt kuralına göre seçer.

Bu bir *politika* değerlendirmesidir; üretim modeline ağırlık yazmaz, LoRA veya
fine-tuning yapmaz. Sonuç runtime/evals/ altına yazılır; B daha kötüyse geri
alma önerisi raporlanır.

Kullanım:
    python tools/eval_learning.py
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "ahos_core" / "runtime"
OUT = RUNTIME / "evals"
_EDIT = re.compile(r"dosyas[ıi]n[ıi]n sonuna|sonuna .*(ekle|yorum|satır)", re.I)

# Eğitim kümesi: geçmiş oranlar (A için) — değerlendirme kümesinden ayrıdır.
TRAIN = {"simple_edit": (18, 2), "executor": (8, 12), "document": (6, 4)}

# Değerlendirme kümesi: 40 görev, gizli doğru etiket.
EVAL_TASKS = (
    [{"objective": f"app/mod_{i}.py dosyasının sonuna şu satırı ekle: # p{i}",
      "label": "simple_edit"} for i in range(20)]
    + [{"objective": f"Yeni modül tasarla: servis {i} için mimari ve test planı",
        "label": "executor"} for i in range(14)]
    + [{"objective": f"Bu haftanın bölüm planı ve sahne listesini hazırla {i}",
        "label": "document"} for i in range(6)]
)


def strategy_history_rate(task: dict) -> str:
    best = max(TRAIN.items(), key=lambda item: item[1][0] / max(1, sum(item[1])))
    return best[0]


def strategy_evidence_grounded(task: dict) -> str:
    objective = str(task.get("objective") or "")
    if _EDIT.search(objective):
        return "simple_edit"
    if "plan" in objective.casefold() or "tasar" in objective.casefold():
        return "document"
    return "executor"


def evaluate() -> dict:
    rows = []
    for task in EVAL_TASKS:
        rows.append({
            "objective": task["objective"], "label": task["label"],
            "a": strategy_history_rate(task), "b": strategy_evidence_grounded(task),
        })
    total = len(rows)
    a_ok = sum(1 for row in rows if row["a"] == row["label"])
    b_ok = sum(1 for row in rows if row["b"] == row["label"])
    result = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "schema": "ahos.learning-eval.v1",
        "evaluation_set": "held-out synthetic policy set (40 tasks) — not production model weights",
        "methods": {
            "history_rate": {"correct": a_ok, "accuracy": round(a_ok / total, 3)},
            "evidence_grounded": {"correct": b_ok, "accuracy": round(b_ok / total, 3)},
        },
        "delta": round((b_ok - a_ok) / total, 3),
        "winner": "evidence_grounded" if b_ok > a_ok else (
            "history_rate" if a_ok > b_ok else "tie"),
        "rollback_recommended": b_ok < a_ok,
        "note": "policy-level comparison only; no fine-tuning or weight change",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"learning-eval-{time.strftime('%Y%m%dT%H%M%S')}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
