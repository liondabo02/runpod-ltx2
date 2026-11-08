import io
import os
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

os.environ["AHOS_DOCUMENT_QA"] = "1"
os.environ.setdefault("AHOS_MISSION_TIMEOUT_SECONDS", "900")

from ahos.owner_console import build_default_console

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
console = build_default_console(R)
console.handle("veri departmanı kur") if "data" not in [d.department_id for d in []] else None

spec = console.book.get("data")
if spec is None:
    print("data departmanı yok")
    raise SystemExit(1)

result = console.run_department_mission(
    spec,
    "Kuyruk durum raporu v3: status sayıları ve departman dağılımı (JSON)",
)
print("status:", result.status)
print("mesaj:", str(result.message)[:200])
if result.mission:
    for step in result.mission.steps or ():
        print("  ", step.step.step_id, step.stage.value, "|", str(step.worker_summary)[:120])
