import io
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
WWW = R / "projects" / "mipiluna" / "www"

print("=== OYUN (www) ===")
files = [p for p in WWW.rglob("*") if p.is_file()]
print("dosya:", len(files), "| toplam MB:", round(sum(p.stat().st_size for p in files) / 1e6, 1))
index = WWW / "index.html"
if index.exists():
    text = index.read_text(encoding="utf-8", errors="replace")
    print("index.html:", len(text), "karakter")
    if "<title>" in text:
        print("baslik:", text.split("<title>")[1].split("</title>")[0])
    print("script etiketi:", text.count("<script"), "| audio:", text.count("<audio"), "| voices referansi:", text.count("voices/"))
top = sorted(files, key=lambda p: p.stat().st_size, reverse=True)[:8]
for p in top:
    print(f"  {p.relative_to(WWW)} · {round(p.stat().st_size/1024)} KB")

print("\n=== DEPARTMANLAR ===")
book = json.loads((R / "departments.json").read_text(encoding="utf-8"))
deps = book.get("departments") if isinstance(book, dict) else book
for dep in deps:
    print(f"  {dep.get('department_id'):14} · {dep.get('name','')[:32]:32} · işçi {len(dep.get('workers') or [])}")

print("\n=== KUYRUK / DEPARTMAN ===")
con = sqlite3.connect(R / "company-service.db")
for row in con.execute(
    "select substr(mission_id,5,12) d, status, count(*) from missions "
    "where status!='cancelled' group by d,status order by 3 desc limit 14"
):
    print("  ", row[0], row[1], row[2])
