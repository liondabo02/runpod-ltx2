import io
import json
import shutil
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
book = R / "departments.json"
data = json.loads(book.read_text(encoding="utf-8"))
deps = data.get("departments") if isinstance(data, dict) else data

existing = {str(d.get("department_id")) for d in deps}
if "arge" in existing:
    print("Ar-Ge departmanı zaten var")
    raise SystemExit(0)

template = next((d for d in deps if str(d.get("department_id")) == "data"), deps[0])
clone = json.loads(json.dumps(template))
clone["department_id"] = "arge"
clone["name"] = "Ar-Ge Departmanı"
clone["mission"] = "Tüm departmanlar için sürekli araştırma, ölçüm ve iyileştirme"
clone["status"] = "active"
clone["source"] = "owner"
clone["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
clone["keywords"] = ["ar-ge", "araştırma", "iyileştirme", "ölçüm", "deney", "benchmark"]

workers = clone.get("workers") or []
if workers:
    base = workers[0]
    new_workers = []
    for index, suffix in enumerate(("lead", "analyst", "tester")):
        worker = json.loads(json.dumps(base))
        worker["worker_id"] = f"arge-{suffix}"
        worker["name"] = {"lead": "Ar-Ge Lideri", "analyst": "Ar-Ge Analisti", "tester": "Ar-Ge Test Uzmanı"}[suffix]
        new_workers.append(worker)
    clone["workers"] = new_workers

deps.append(clone)
if isinstance(data, dict):
    data["departments"] = deps
    payload = data
else:
    payload = deps

shutil.copy2(book, R / f"backups/departments-{time.strftime('%Y%m%d-%H%M%S')}.json")
book.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print("eklendi · departman sayısı:", len(deps))
print("işçiler:", [w.get("worker_id") for w in clone.get("workers") or []])
