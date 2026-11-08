import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

from ahos.owner_console import build_default_console
from ahos.queue_drain import drain

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
console = build_default_console(R)

results = drain(console, owner="dept-test", limit=2)
print("işlenen:", len(results))
for item in results:
    mission = getattr(item, "mission", None)
    mid = mission.mission_id if mission else "?"
    print(f"  {mid[:44]:44} {item.status:10} {str(item.message)[:110]}")
