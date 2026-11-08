"""G006: kanıtsız işçiler için rolüne uygun gerçek görev önerileri üretir.

Kural: sahte başarı üretmez. Her öneri gerçek bir teslim üretir (belge veya
dosya değişikliği) ve kabul kapısından geçmeden tamamlanmış sayılmaz.

Varsayılan kuru çalışmadır; `--apply` yalnız sınırlı sayıda gerçek görevi
kuyruğa yazar. Görev, işçinin departmanına yönlendirilir; işçinin fiilen adımda
yer alması yürütücü atamasına bağlıdır (kanıt ancak gerçek adım kaydıyla oluşur).

Kullanım:
    python tools/worker_tasks.py --limit 10
    python tools/worker_tasks.py --limit 5 --apply
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
RUNTIME = CORE / "runtime"
sys.path.insert(0, str(CORE))

FOCUS = {
    "software": "küçük bir test veya güvenli kod iyileştirmesi",
    "quality": "bağımsız hata bulma ve regresyon kontrolü",
    "creative": "sahne/senaryo tutarlılığı denetimi",
    "oyun": "oynanış dengesi ve hata senaryosu analizi",
    "data": "örnek veriyle hesap doğrulama",
    "finance": "örnek veriyle hesap doğrulama",
    "marketing": "araştırma kaynaklarını karşılaştırma",
    "sales": "müşteri itirazı ve fiyat senaryosu analizi",
    "support": "SSS ve yanıt şablonu doğrulama",
    "operations": "süreç adımları ve darboğaz kontrolü",
    "infrastructure": "servis sağlık kontrolü",
    "guvenlik": "bağımlılık ve yetki denetimi",
    "hukuk": "uyum kontrol listesi",
    "ai-platform": "model maliyet/kalite karşılaştırması",
    "research": "kaynak ve iddia doğrulama",
    "holding": "portföy durumu ve öncelik özeti",
    "genel": "süreç iyileştirme notu",
}


def _roster() -> list[tuple[str, str, str]]:
    payload = json.loads((RUNTIME / "departments.json").read_text(encoding="utf-8"))
    departments = payload.get("departments") if isinstance(payload, dict) else payload
    rows = []
    for dep in departments:
        dep_id = str(dep.get("department_id") or "")
        for worker in dep.get("workers") or []:
            wid = str(worker.get("worker_id") or "")
            if wid:
                rows.append((dep_id, wid, str(worker.get("name") or wid)))
    return rows


def _verified() -> set[str]:
    verified = set()
    for path in (RUNTIME / "cognition").glob("*.json"):
        if path.name.startswith(("_", ".")):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (payload.get("evidence") or {}).get("status") == "verified":
            verified.add(str(payload.get("worker_id")))
    return verified


def proposals(limit: int | None = None) -> list[dict]:
    verified = _verified()
    stamp = int(time.time())
    rows = []
    for dep_id, worker, name in _roster():
        if worker in verified:
            continue
        focus = FOCUS.get(dep_id, FOCUS["genel"])
        rows.append({
            "mission_id": f"CMD-{dep_id}-v4task-{stamp}-{len(rows)}",
            "department": dep_id,
            "worker": worker,
            "objective": (f"Tasarım dokümanı üret: {name} ({worker}) için {focus}. "
                          "İçerik: amaç, kapsam, adım listesi, riskler, kabul kriteri."),
        })
        if limit is not None and len(rows) >= limit:
            break
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    rows = proposals(limit=max(1, args.limit))
    print(json.dumps({"proposed": len(rows), "evidence_less": len(proposals(None)),
                      "applied": bool(args.apply)}, ensure_ascii=False))
    for row in rows:
        print(f"  {row['mission_id'][:42]:42} {row['department']:13} {row['worker']}")
    if not args.apply:
        return 0
    from ahos.autonomous_company import PersistentMissionQueue

    queue = PersistentMissionQueue(RUNTIME / "company-service.db")
    created = 0
    for row in rows:
        queue.enqueue(mission_id=row["mission_id"], objective=row["objective"],
                      primary_department=row["department"], max_attempts=1,
                      replace_existing=True)
        created += 1
    print(json.dumps({"created": created}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
