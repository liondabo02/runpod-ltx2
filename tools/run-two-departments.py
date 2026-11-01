import io
import os
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

os.environ["AHOS_DOCUMENT_QA"] = "1"
os.environ["AHOS_PROVIDER_CHAIN"] = "1"
os.environ["AHOS_MISSION_TIMEOUT_SECONDS"] = "900"

from ahos.owner_console import build_default_console

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
console = build_default_console(R)

stamp = time.strftime("%H%M%S")
for department in ("data", "guvenlik"):
    spec = console.book.get(department)
    if spec is None:
        print(department, "yok")
        continue
    started = time.time()
    result = console.run_department_mission(
        spec,
        f"Kısa durum raporu yaz (sürüm {stamp}): görev sayıları ve 3 öneri",
    )
    print(f"[{department}] {time.time()-started:.0f}s · {result.status} · {str(result.message)[:120]}")
    for step in (result.mission.steps if result.mission else ()):
        print("   ", step.step.step_id, step.stage.value, "|", str(step.worker_summary)[:100])
