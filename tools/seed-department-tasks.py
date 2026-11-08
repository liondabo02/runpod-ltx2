import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

from ahos.autonomous_company import PersistentMissionQueue

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
queue = PersistentMissionQueue(R / "company-service.db")

TASKS = [
    ("data", "Kuyruk durum raporu üret: status sayıları ve departman dağılımı (JSON)",
     "CMD-data-kuyruk-raporu-a1"),
    ("finance", "Model harcama özetini CSV olarak yaz: model, çağrı, USD",
     "CMD-finance-harcama-ozeti-a1"),
    ("guvenlik", "Son 24 saatte ücretli model çağrısı var mı denetle ve raporla",
     "CMD-guvenlik-ucret-denetimi-a1"),
    ("quality", "Son 10 tamamlanan görevin kabul kapısı sonuçlarını listele",
     "CMD-quality-kapi-raporu-a1"),
    ("research", "Mipiluna oyunu için 3 geliştirme önerisi yaz (kısa, gerekçeli)",
     "CMD-research-oyun-onerileri-a1"),
    ("marketing", "Mipiluna için veliye yönelik 3 cümlelik tanıtım metni yaz",
     "CMD-marketing-tanitim-metni-a1"),
]

created = []
for dept, objective, mission_id in TASKS:
    try:
        queue.enqueue(
            mission_id=mission_id,
            objective=objective,
            primary_department=dept,
            max_attempts=1,
            replace_existing=True,
        )
        created.append(mission_id)
    except Exception as exc:  # noqa: BLE001
        print(f"HATA {dept}: {exc}")

print("kuyruğa eklenen:", len(created))
for mission in created:
    print("  ", mission)

import sqlite3

con = sqlite3.connect(R / "company-service.db")
counts = {row[0]: row[1] for row in con.execute("select status, count(*) from missions group by status")}
print("durum:", counts)
