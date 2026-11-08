import io
import os
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

os.environ.update({
    "AHOS_LLM_BASE_URL": "http://127.0.0.1:11500/v1",
    "AHOS_LLM_MODEL": "qwen2.5-coder:3b",
    "AHOS_LLM_API_KEY": "local-only",
    "AHOS_LLM_FREE": "1",
    "AHOS_ALLOW_PAID_LLM": "0",
    "AHOS_LLM_TIMEOUT": "300",
    "AHOS_LLM_MAX_TOKENS": "700",
})

from ahos.document_executor import make_document_executor
from ahos.llm_executor import load_settings
from ahos.worker_runtime import WorkItem

print("settings:", "var" if load_settings() is not None else "YOK")
if load_settings() is None:
    raise SystemExit(1)

item = WorkItem(
    task_id="CMD-data-test-belge",
    title="Kuyruk durum raporu üret",
    department="data",
    required_capabilities=frozenset({"analysis"}),
)
executor = make_document_executor(Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\artifacts"))
started = time.time()
result = executor(item, "data-01")
print(f"sure: {time.time()-started:.1f}s")
print("success:", result.success)
print("summary:", str(result.summary)[:160])
for path in result.artifacts or ():
    p = Path(path)
    print("dosya:", p, p.stat().st_size if p.exists() else "yok")
