import io
import os
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

os.environ.update({
    "AHOS_EXECUTOR": "model",
    "AHOS_LLM_BASE_URL": "http://127.0.0.1:11500/v1",
    "AHOS_LLM_MODEL": "qwen2.5-coder:7b",
    "AHOS_LLM_API_KEY": "local-only",
    "AHOS_LLM_FREE": "1",
    "AHOS_LLM_TIMEOUT": "300",
    "AHOS_LLM_MAX_TOKENS": "700",
    "AHOS_LLM_FOCUSED": "1",
    "AHOS_MODEL_BROWSER_CHECK": "0",
    "AHOS_MISSION_TIMEOUT_SECONDS": "600",
})

from ahos.owner_console import build_default_console

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
console = build_default_console(R)
spec = console.book.get("oyun")

# Kasıtlı olarak VAR OLMAYAN hedef: eski hataların birebir kopyası.
objective = "www/kart-stil.css dosyasının sonuna şu yorumu ekle: /* ahos-retarget-testi */"
started = time.time()
result = console.run_department_mission(spec, objective)
elapsed = time.time() - started

print(f"süre: {elapsed:.0f}s | durum: {result.status}")
print("mesaj:", str(result.message)[:200])
for step in (result.mission.steps if result.mission else ()):
    print("  ", step.step.step_id, step.stage.value, "|", str(step.worker_summary)[:130])

# hedef çevrildi mi?
import json

audit = R / "audit.jsonl"
if audit.exists():
    for line in audit.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("event") == "mission.retargeted":
            print("retarget:", json.dumps(row.get("detail"), ensure_ascii=False)[:160])
