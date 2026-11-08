import io
import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
book = R / "departments.json"
data = json.loads(book.read_text(encoding="utf-8"))
deps = data.get("departments") if isinstance(data, dict) else data
if isinstance(deps, dict):
    deps = list(deps.values())

print("önce:", len(deps), "departman")
print("ilk kaydın alanları:", sorted(deps[0].keys()) if deps else "-")

con = sqlite3.connect(R / "company-service.db")
usage = {}
for row in con.execute("select mission_id, status, count(*) from missions group by mission_id"):
    pass
counts = {r[0]: r[1] for r in con.execute(
    "select substr(mission_id, 5, instr(substr(mission_id,5), '-')-1) d, count(*) from missions group by d")}
print("kuyrukta departman kullanımı:", counts)

dupes = [d for d in deps if str(d.get("department_id", "")).startswith("genel-")
         and str(d.get("department_id")) != "genel"]
print("kopya aday:", [d.get("department_id") for d in dupes])

keep = []
removed = []
for dep in deps:
    did = str(dep.get("department_id", ""))
    if did in {str(x.get("department_id")) for x in dupes}:
        # yalnız kuyrukta hiç görevi olmayan kopyaları kaldır
        if counts.get(did, 0) == 0:
            removed.append(did)
            continue
    keep.append(dep)

if removed:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    shutil.copy2(book, R / f"backups/departments-{stamp}.json")
    if isinstance(data, dict):
        data["departments"] = keep
        book.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        book.write_text(json.dumps(keep, ensure_ascii=False, indent=2), encoding="utf-8")
print("kaldırılan:", removed)
print("sonra:", len(keep), "departman")
