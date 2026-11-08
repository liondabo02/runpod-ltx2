import io
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
from ahos import skills

book = json.loads((R / "departments.json").read_text(encoding="utf-8"))
deps = book.get("departments") if isinstance(book, dict) else book

metrics = defaultdict(lambda: {"runs": 0, "ok": 0})
ledger = R / "worker-metrics.jsonl"
for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines()[-5000:]:
    try:
        row = json.loads(line)
    except Exception:
        continue
    dept = str(row.get("department") or "?")
    metrics[dept]["runs"] += 1
    metrics[dept]["ok"] += 1 if row.get("success") else 0

blocked = defaultdict(Counter)
con = sqlite3.connect(R / "company-service.db")
for mission, error in con.execute("select mission_id, last_error from missions where status='blocked'"):
    dept = mission.split("-")[1] if "-" in mission else "?"
    text = (error or "").lower()
    key = ("kilit" if "kilit" in text else
           "zaman aşımı" if "timeout" in text or "zaman aşımı" in text else
           "QA" if "qa failed" in text or "unverified" in text else
           "yürütücü" if "executor_unavailable" in text or "yürütücü" in text else
           "hedef dosya" if "dosya yok" in text or "hedef" in text else "diğer")
    blocked[dept][key] += 1

print(f"{'DEPARTMAN':16} {'İŞÇİ':>4} {'BAŞARI':>7} {'KOŞU':>5}  BAŞLICA ENGEL")
for dep in sorted(deps, key=lambda d: str(d.get("department_id"))):
    did = str(dep.get("department_id"))
    stat = metrics.get(did, {"runs": 0, "ok": 0})
    rate = (stat["ok"] / stat["runs"] * 100) if stat["runs"] else 0.0
    top = blocked.get(did, Counter()).most_common(1)
    label = f"{top[0][0]} x{top[0][1]}" if top else "-"
    print(f"{did:16} {len(dep.get('workers') or []):>4} {rate:>6.1f}% {stat['runs']:>5}  {label}")

print("\nzorunlu ders enjeksiyonu testi:")
for probe in ("Oyuna seslendirme ekle", "Kuyruk raporu üret", "Jenerik videosu hazırla", "Harcama özeti yaz"):
    cards = skills.retrieve(R, probe, limit=2)
    top = cards[0].get("rule", "")[:70] if cards else "-"
    print(f"  {probe:32} -> {top}")

print("\nbilgi ağı:", skills.stats(R))
