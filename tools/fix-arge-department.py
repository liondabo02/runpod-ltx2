import io
import json
import shutil
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
book = R / "departments.json"
data = json.loads(book.read_text(encoding="utf-8"))
deps = data.get("departments") if isinstance(data, dict) else data

data_dep = next(d for d in deps if str(d.get("department_id")) == "data")
arge = next((d for d in deps if str(d.get("department_id")) == "arge"), None)
if arge is None:
    print("arge bulunamadı")
    raise SystemExit(1)

KEYWORDS = ["ar-ge", "araştırma", "iyileştirme", "ölçüm", "deney", "benchmark", "analiz"]

def capability(name: str, authority: str, description: str) -> dict:
    return {"name": f"arge.{name}", "description": description, "authority": authority}

arge["name"] = "Ar-Ge Departmanı"
arge["mission"] = "Tüm departmanlar için sürekli araştırma, ölçüm ve iyileştirme"
arge["keywords"] = KEYWORDS
arge["capabilities"] = [
    capability("oversight", "B", "Ar-Ge gözetimi: ölçüm sonuçlarını izler."),
    capability("planning", "A", "Ar-Ge planlaması: iyileştirme turunu planlar."),
    capability("routing", "A", "Ar-Ge yönlendirmesi: dersleri doğru departmana yönlendirir."),
    capability("task_decomposition", "B", "Ar-Ge görev bölme."),
    capability("analytics", "B", "Hata ve başarı analizi."),
    capability("experiment", "B", "Deney tasarımı ve ölçüm kriteri."),
    capability("python", "B", "Ölçüm betikleri (Python)."),
    capability("reporting", "B", "Ar-Ge raporu ve müfredat yazımı."),
]
arge["workers"] = [
    {
        "worker_id": "arge-manager",
        "name": "Ar-Ge Yöneticisi",
        "role": "department_manager",
        "capabilities": ["oversight", "planning", "routing", "task_decomposition"],
    },
    {
        "worker_id": "arge-analyst",
        "name": "Ar-Ge Analisti",
        "role": "data_analyst",
        "capabilities": ["analytics", "experiment", "python"],
    },
    {
        "worker_id": "arge-writer",
        "name": "Ar-Ge Rapor Sorumlusu",
        "role": "data_analyst",
        "capabilities": ["reporting", "experiment"],
    },
]

if isinstance(data, dict):
    data["departments"] = deps
    payload = data
else:
    payload = deps

shutil.copy2(book, R / f"backups/departments-{time.strftime('%Y%m%d-%H%M%S')}.json")
book.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print("arge düzeltildi")

from ahos.departments import DepartmentBook

try:
    loaded = DepartmentBook(book, seed=False)
    print("doğrulama: GEÇTİ · departman:", len(loaded.all()))
except Exception as exc:  # noqa: BLE001
    print("doğrulama HATASI:", exc)
