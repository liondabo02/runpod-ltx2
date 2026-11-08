"""Herkesi çalıştır: 19 departmanın tamamına birer görev.

- Proje bağlı departmanlar (oyun, software): gerçek dosya düzenlemesi (deterministik).
- Diğerleri: kısa, somut rapor görevi (belge yürütücüsü).

Amaç: ofisteki hiçbir departman boş kalmasın; tek turda herkes iş alsın.
"""

import io
import json
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

from ahos.autonomous_company import PersistentMissionQueue

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
book = json.loads((R / "departments.json").read_text(encoding="utf-8"))
deps = book.get("departments") if isinstance(book, dict) else book

FILE_TASKS = {
    "oyun": ("www/oyun-yazi.js", "// allhands"),
    "software": ("ahos/audit.py", "# allhands"),
}

OBJECTIVES = {
    "arge": "Bu haftanın en zayıf 2 departmanını ve nedenini 5 maddede yaz",
    "creative": "Mipiluna için 3 sahnelik kısa bir jenerik senaryosu yaz",
    "data": "Kuyruk durumunu özetleyen 1 sayfalık rapor üret",
    "finance": "Bu ayın tahmini maliyetini 3 kalemde çıkar",
    "guvenlik": "Son 7 günün güvenlik risklerini 5 maddede listele",
    "hukuk": "Çocuk oyunu için KVKK uyum kontrol listesi yaz",
    "holding": "Holdingin 1 haftalık öncelik listesini 5 maddeye indir",
    "marketing": "Mipiluna için 3 kanallı tanıtım planı yaz",
    "operations": "Görev akışındaki 3 darboğazı ve çözümünü yaz",
    "quality": "Kabul kriterleri kontrol listesini güncelle",
    "research": "Benzer çocuk oyunlarını 5 kriterde karşılaştır",
    "support": "En sık 3 kullanıcı sorununu ve yanıtını yaz",
    "ai-platform": "Model hattı için 3 iyileştirme önerisi yaz",
    "infrastructure": "Tünel ve daemon için 3 sağlamlaştırma adımı yaz",
    "sales": "Teklif şablonu için 5 başlık yaz",
    "genel": "Ofisteki işlerin 1 günlük özetini yaz",
}

queue = PersistentMissionQueue(R / "company-service.db")
stamp = int(time.time())
created = []

for dep in deps:
    dep_id = str(dep.get("department_id") or "")
    if not dep_id:
        continue
    if dep_id in FILE_TASKS:
        rel, prefix = FILE_TASKS[dep_id]
        objective = f"{rel} dosyasının sonuna şu yorumu ekle: {prefix}-{stamp}"
    else:
        objective = OBJECTIVES.get(dep_id, f"{dep_id} departmanı için kısa bir durum notu yaz")
    mission_id = f"CMD-{dep_id}-allhands-{stamp}"
    try:
        queue.enqueue(
            mission_id=mission_id,
            objective=objective,
            primary_department=dep_id,
            max_attempts=1,
            replace_existing=True,
        )
        created.append((dep_id, mission_id, objective[:60]))
    except Exception as exc:
        print("hata:", dep_id, exc)

print(f"görev verilen departman: {len(created)}/{len(deps)}")
for dep_id, mission_id, objective in created:
    print(f"  {dep_id:14} {objective}")
