"""10 görevlik ölçüm partisi: panelden verilen iş gerçekten bitiyor mu?

Her görev tek dosya + tek somut değişiklik. Daemon tahliyesi işler.
Sonuç: kaç tamamlandı, kaç saniye, dosya gerçekten değişti mi.
"""

import io
import sqlite3
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

from ahos.autonomous_company import PersistentMissionQueue

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
stamp = int(time.time())

TASKS = [
    ("software", "ahos/audit.py", "# olcum"),
    ("software", "ahos/approval.py", "# olcum"),
    ("software", "ahos/acceptance.py", "# olcum"),
    ("software", "ahos/autonomy.py", "# olcum"),
    ("oyun", "www/card-keys.js", "// olcum"),
    ("oyun", "www/oyun-yazi.js", "// olcum"),
    ("oyun", "www/oyun-ipucu.js", "// olcum"),
    ("oyun", "www/hata-siniri.js", "// olcum"),
    ("oyun", "www/mobile.js", "// olcum"),
    ("oyun", "www/alive.js", "// olcum"),
]

queue = PersistentMissionQueue(R / "company-service.db")
created = []
for index, (department, rel, prefix) in enumerate(TASKS, start=1):
    mission_id = f"CMD-{department}-olcum10-{stamp}-{index}"
    objective = f"{rel} dosyasının sonuna şu yorumu ekle: {prefix}-{stamp}-{index}"
    queue.enqueue(
        mission_id=mission_id,
        objective=objective,
        primary_department=department,
        max_attempts=1,
        replace_existing=True,
    )
    created.append((mission_id, department, rel, f"{prefix}-{stamp}-{index}"))

print("kuyruğa eklenen:", len(created))
for mission_id, department, rel, marker in created:
    print(f"  {department:9} {rel}")

WAIT = int(sys.argv[1]) if len(sys.argv) > 1 else 240
print(f"\n{WAIT} saniye izleniyor...")
time.sleep(WAIT)

con = sqlite3.connect(R / "company-service.db")
con.row_factory = sqlite3.Row
print("\n=== SONUÇ ===")
done = 0
for mission_id, department, rel, marker in created:
    row = con.execute("select status, last_error from missions where mission_id=?", (mission_id,)).fetchone()
    status = row["status"] if row else "yok"
    root = R / ("projects/holding-core" if department == "software" else "projects/mipiluna")
    path = root / rel
    changed = path.exists() and marker in path.read_text(encoding="utf-8", errors="replace")
    if status == "completed":
        done += 1
    print(f"  {rel:26} {status:10} dosya_değişti={changed}  {(row['last_error'] or '')[:40] if row else ''}")

counts = {r[0]: r[1] for r in con.execute("select status,count(*) from missions group by status")}
print(f"\ntamamlanan: {done}/10 | kuyruk: {counts}")
