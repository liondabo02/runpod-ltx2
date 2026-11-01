import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2")
R = ROOT / "ahos_core" / "runtime"
LOCK = Path(os.environ.get("AHOS_LOCK_DIR") or Path(os.environ["LOCALAPPDATA"]) / "ahos-locks")


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, timeout=15)
        return str(pid) in out.stdout
    except Exception:  # noqa: BLE001
        return True  # bilinemiyorsa silme


print("=== STALE KİLİT TEMİZLİĞİ ===")
removed = kept = 0
if LOCK.exists():
    for path in LOCK.glob("*"):
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            payload = {}
        pid = int(payload.get("pid") or 0)
        if pid and pid_alive(pid):
            kept += 1
            continue
        # pid yoksa ve 24 saatten eski ise bayat say
        age = time.time() - path.stat().st_mtime
        if pid == 0 and age < 86400:
            kept += 1
            continue
        try:
            path.unlink()
            removed += 1
        except OSError:
            kept += 1
print(f"  silinen: {removed} · korunan: {kept} · kalan: {len(list(LOCK.glob('*'))) if LOCK.exists() else 0}")

print("\n=== SIR DOSYALARI ACL ===")
for name in ("model.env", "runpod.env"):
    path = R / name
    if not path.exists():
        continue
    user = os.environ.get("USERNAME", "")
    try:
        subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:F"],
            capture_output=True, text=True, timeout=20,
        )
        print(f"  {name}: yalnız {user} erişebilir")
    except Exception as exc:  # noqa: BLE001
        print(f"  {name}: ACL ayarlanamadı ({exc})")

print("\n=== DB YEDEĞİ ===")
backups = R / "backups"
backups.mkdir(parents=True, exist_ok=True)
stamp = time.strftime("%Y%m%d-%H%M%S")
target = backups / f"company-service-{stamp}.db"
shutil.copy2(R / "company-service.db", target)
print("  yeni yedek:", target.name, round(target.stat().st_size / 1e6, 1), "MB")
existing = sorted(backups.glob("company-service-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
for old in existing[3:]:
    old.unlink()
print("  toplam yedek:", len(list(backups.glob('company-service-*.db'))))

print("\n=== ENGELSİZ 'DİĞER' NEDEN ÖRNEKLERİ ===")
con = sqlite3.connect(R / "company-service.db")
con.row_factory = sqlite3.Row
for row in con.execute("select mission_id, last_error from missions where status='blocked' limit 12"):
    print(f"  {row['mission_id'][:40]:40} {(row['last_error'] or '')[:80]}")
