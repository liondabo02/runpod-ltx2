"""Sonuç kaydı ve kapsam ayarı.

- record(runtime_dir, department, ok: bool, duration_s: float, blocked: bool) -> dict
  · runtime/outcome.jsonl dosyasına append: {"at","department","ok","duration_s","blocked"}
  · return {"department","success_rate","samples"}
- adjust(runtime_dir, department) -> dict
  · son 20 kaydın başarı oranını hesapla
  · rate < 0.70 → {"scope":"narrow","reason":"başarı düşük"}
  · rate >= 0.90 → {"scope":"wide","reason":"başarı yüksek"}
  · arada → {"scope":"keep"}
  · runtime/outcome-adjust.jsonl dosyasına append
"""

from __future__ import annotations

import json
import time
from pathlib import Path


def record(runtime_dir: str | Path, department: str, ok: bool, duration_s: float, blocked: bool = False) -> dict:
    """Sonuç kaydı.

    Args:
        runtime_dir: runtime dizini
        department: departman adı
        ok: başarılı mı
        duration_s: süre (saniye)
        blocked: engellendi mi

    Returns:
        {"department","success_rate","samples"}
    """
    runtime = Path(runtime_dir)
    log_path = runtime / "outcome.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    entry = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "department": department,
        "ok": ok,
        "duration_s": duration_s,
        "blocked": blocked,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    # success_rate ve samples hesapla
    scores: list[bool] = []
    if log_path.exists():
        try:
            for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]:
                try:
                    row = json.loads(line)
                    scores.append(row.get("ok", False))
                except json.JSONDecodeError:
                    continue
        except OSError:
            pass
    
    passed = sum(1 for s in scores if s)
    total = len(scores)
    rate = round(passed / total, 2) if total > 0 else 0.0
    
    return {"department": department, "success_rate": rate, "samples": total}


def adjust(runtime_dir: str | Path, department: str) -> dict:
    """Kapsam ayarı.

    Args:
        runtime_dir: runtime dizini
        department: departman adı

    Returns:
        {"scope","reason"}
        scope: "narrow", "wide", "keep"
        reason: açıklama
    """
    runtime = Path(runtime_dir)
    log_path = runtime / "outcome.jsonl"
    
    # Son 20 kaydı al
    scores: list[bool] = []
    if log_path.exists():
        try:
            for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]:
                try:
                    row = json.loads(line)
                    scores.append(row.get("ok", False))
                except json.JSONDecodeError:
                    continue
        except OSError:
            pass
    
    if not scores:
        return {"scope": "keep", "reason": "veri yok"}
    
    passed = sum(1 for s in scores if s)
    total = len(scores)
    rate = passed / total
    
    if rate < 0.70:
        scope = "narrow"
        reason = "başarı düşük"
    elif rate >= 0.90:
        scope = "wide"
        reason = "başarı yüksek"
    else:
        scope = "keep"
        reason = "mevcut"
    
    # adjust.jsonl'a kaydet
    adj_path = runtime / "outcome-adjust.jsonl"
    adj_path.parent.mkdir(parents=True, exist_ok=True)
    adj_entry = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "department": department,
        "scope": scope,
        "reason": reason,
        "rate": rate,
        "samples": total,
    }
    with open(adj_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(adj_entry, ensure_ascii=False) + "\n")
    
    return {"scope": scope, "reason": reason}
