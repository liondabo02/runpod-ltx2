"""CEO brain: diagnose failures, name the root cause and hand the fix to a department.

The CEO should not only report numbers. This module turns the mission queue into
a diagnosis: what failed, why (root cause), the evidence, how to fix it and which
department owns the fix. It can also dispatch the fix as a goal for that
department so the holding corrects itself.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path

CAUSES = {
    "queue_stuck": (
        "Görev sıraya girdi ama hiç çalışmadı",
        "Kuyruk kilidi / bayat iş kalemi",
        "Sahiplik ve kira geçmişini denetle; tamamlanmış adımı sıfırlama, sınırlı kurtarma planı çıkar",
        "software",
    ),
    "patch_missing": (
        "Yama hedefi dosyada bulunamadı",
        "Model, find metnini dosyadan birebir kopyalamıyor",
        "Onarım turunda gerçek dosya gövdesini ver; esnek boşluk eşleşmesi kullan",
        "software",
    ),
    "patch_ambiguous": (
        "Yama hedefi birden fazla yerde bulundu",
        "Aranan metin kısa/tekrarlı; tek eşleşme yok",
        "Daha uzun bağlam iste veya dosya+satır aralığı ver",
        "software",
    ),
    "json_parse": (
        "Model yanıtı JSON olarak çözümlenemedi",
        "Yanıt ```json çiti veya ek metin içeriyor",
        "Çitleri sök, tek JSON nesnesi iste, kesilirse max_tokens artır",
        "software",
    ),
    "acceptance": (
        "Değişiklik uygulandı ama kabul kapısı düştü",
        "Projenin kendi testi/derlemesi kırıldı",
        "Düşen testi okuyup düzelt; kapı geçmeden teslim sayma",
        "oyun",
    ),
    "approval": (
        "Değişiklik onay bekliyor",
        "Orta/yüksek risk sınıflandı",
        "Riski düşür (küçük yama) veya sahibinden onay al",
        "holding",
    ),
    "budget": (
        "Model bütçesi doldu",
        "Günlük tavan aşıldı",
        "Mevcut bütçeyi koru; ücretsiz uç uygunsa kullan, değilse beklet ve sahibine bildir",
        "holding",
    ),
    "model": (
        "Model çağrısı başarısız",
        "Ağ/429/kota",
        "Yedek modele geç, sonra tekrar dene",
        "software",
    ),
}
CAUSES.update({
    "authorization": ("Model yetkilendirmesi reddedildi", "HTTP 401/403 erişim hatası",
                      "Anahtarı göstermeden erişim ve endpoint yapılandırmasını doğrula; aynı isteği körlemesine tekrarlama", "ai-platform"),
    "unknown": ("Nedeni henüz doğrulanmamış hata", "Mevcut kanıt kök nedeni belirlemiyor",
                "Ham hata kaydını incele ve izole yeniden üretim testi oluştur", "software"),
})


def _classify(text: str) -> str:
    lowered = text.casefold()
    if not lowered.strip():
        return "queue_stuck"
    if re.search(r"\b(?:401|403)\b", lowered):
        return "authorization"
    matches = re.search(r"\b(\d+)\s+kez bulundu", lowered)
    if matches and int(matches.group(1)) == 0:
        return "patch_missing"
    if matches and int(matches.group(1)) > 1:
        return "patch_ambiguous"
    if "bulunamadı" in lowered or "bulunamadi" in lowered:
        return "patch_missing"
    if "json" in lowered:
        return "json_parse"
    if "doğrulama başarısız" in lowered or "kabul" in lowered and "düştü" in lowered:
        return "acceptance"
    if "onay bekliyor" in lowered:
        return "approval"
    if "bütçe" in lowered:
        return "budget"
    if "model" in lowered and ("başarısız" in lowered or "429" in lowered):
        return "model"
    if "sahiplenilemedi" in lowered or "başka işçide" in lowered or "kapalı" in lowered:
        return "queue_stuck"
    return "unknown"


def collect(runtime_dir: str | Path, limit: int = 200) -> list[dict]:
    """Read recent blocked missions from the queue."""

    db = Path(runtime_dir) / "company-service.db"
    if not db.is_file():
        return []
    try:
        con = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "select mission_id, objective, primary_department, result_json, last_error "
            "from missions where status in ('blocked','failed') order by rowid desc limit ?",
            (limit,),
        ).fetchall()
        con.close()
    except sqlite3.Error:
        return []
    result: list[dict] = []
    for row in rows:
        try:
            payload = json.loads(row["result_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        steps = payload.get("steps") or []
        if not isinstance(steps, list):
            steps = []
        text = " ".join([
            str(row['last_error'] or ''), str(payload.get('reason') or ''),
            *[str(step.get('reason') or step.get('worker_summary') or '')
              for step in steps if isinstance(step, dict)],
        ]).strip()
        result.append(
            {
                "mission_id": str(row["mission_id"]),
                "objective": str(row["objective"]),
                "department": str(row["primary_department"] or ""),
                "summary": text[:300],
                "cause": _classify(text),
            }
        )
    return result


def diagnose(runtime_dir: str | Path) -> dict:
    """Group failures by cause with evidence and a concrete fix."""

    rows = collect(runtime_dir)
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        cause = str(row['cause'])
        # A backend acceptance failure belongs to the backend department,
        # not always the game team. Keep distinct owners in distinct findings.
        owner = str(row.get('department') or '') if cause == 'acceptance' else ''
        grouped.setdefault((cause, owner), []).append(row)
    findings = []
    for (cause, origin), items in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True):
        label, root, fix, owner = CAUSES.get(cause, CAUSES["queue_stuck"])
        owner = origin or owner
        findings.append(
            {
                "cause": cause,
                "label": label,
                "count": len(items),
                "root_cause": root,
                "fix": fix,
                "owner": owner,
                "evidence": [f"{item['mission_id'][-18:]} · {item['objective'][:50]}" for item in items[:3]],
            }
        )
    return {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "failures": len(rows),
        "findings": findings,
        "top": findings[0] if findings else None,
    }


def explain(diagnosis: dict) -> str:
    """A short, concrete Turkish explanation: what, why, evidence, fix, owner."""

    if not diagnosis.get("findings"):
        return "Engellenen görev yok; kök neden analizi gerektiren bir birikim görünmüyor."
    lines = [f"{diagnosis['failures']} engelli görev bulundu. Kök nedenler:"]
    for index, item in enumerate(diagnosis["findings"][:3], start=1):
        lines.append(
            f"{index}) {item['label']} ({item['count']} görev). "
            f"Kök neden: {item['root_cause']}. "
            f"Çözüm: {item['fix']}. Sorumlu: {item['owner']}."
        )
        if item["evidence"]:
            lines.append("   Kanıt: " + "; ".join(item["evidence"][:2]))
    return "\n".join(lines)


def dispatch(runtime_dir: str | Path, limit: int = 2) -> list[dict]:
    """Open a fix goal for the top causes in the owning department."""

    from .goals import create

    runtime = Path(runtime_dir)
    diagnosis = diagnose(runtime)
    created: list[dict] = []
    for item in diagnosis["findings"][:limit]:
        title = f"Sorun giderme: {item['label']} · {item['fix'][:70]}"
        goal = create(runtime, title, item["owner"], template="default")
        created.append({"goal_id": goal.goal_id, "title": goal.title, "department": item["owner"]})
    return created
