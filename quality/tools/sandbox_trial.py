"""Three-task trial in an isolated sandbox copy.

Never touches the live project: the Mipiluna tree is copied to a temp folder,
the worker runs there, and the verdict is computed from real file diffs plus the
project's own acceptance gate (not from a browser load).

    python quality/tools/sandbox_trial.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ahos_core"))

from ahos.daemon import _load_model_env  # noqa: E402
from ahos.delivery import diff_trees, snapshot_tree  # noqa: E402
from ahos.llm_executor import load_settings, make_model_executor  # noqa: E402

TASKS = [
    "Mipiluna ana sayfasina gunun ipucu seridi ekle",
    "Mipiluna oyunlarina tam ekran dugmesi ekle",
    "Mipiluna icin renk koru modu ekle",
]


class _Item:
    def __init__(self, task_id: str, title: str) -> None:
        self.task_id = task_id
        self.title = title


def _acceptance(root: Path) -> tuple[bool, str]:
    gate = root / "tools" / "check_offline.py"
    if not gate.is_file():
        return False, "kabul kapısı yok"
    completed = subprocess.run(
        [sys.executable, str(gate)],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    tail = (completed.stdout or completed.stderr or "").strip().splitlines()
    return completed.returncode == 0, (tail[-1][:120] if tail else "")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    runtime = ROOT / "ahos_core" / "runtime"
    _load_model_env(runtime)
    settings = load_settings()
    if settings is None:
        print("model yapılandırılmadı")
        return 2

    source = runtime / "projects" / "mipiluna"
    sandbox = Path(tempfile.mkdtemp(prefix="ahos-sandbox-"))
    shutil.copytree(source, sandbox, dirs_exist_ok=True)
    artifacts = sandbox.parent / (sandbox.name + "-artifacts")
    executor = make_model_executor(
        sandbox,
        artifacts,
        settings=settings,
        spend_ledger=runtime / "model-spend.jsonl",
        require_approval_over_files=3,
    )

    rows: list[dict] = []
    for index, task in enumerate(TASKS, start=1):
        before = snapshot_tree(sandbox)
        started = time.time()
        result = executor(_Item(f"oyun:sandbox-{index}:produce", task), "sandbox-worker")
        elapsed = round(time.time() - started, 1)
        delta = diff_trees(before, snapshot_tree(sandbox))
        accepted, gate_detail = _acceptance(sandbox)
        row = {
            "task": task,
            "worker_success": bool(getattr(result, "success", False)),
            "summary": str(getattr(result, "summary", ""))[:200],
            "changed_files": delta.changed,
            "changed": list(delta.added + delta.modified)[:6],
            "acceptance_ran": bool(gate_detail),
            "acceptance_passed": accepted,
            "acceptance_detail": gate_detail,
            "verdict": bool(delta.changed) and accepted,
            "seconds": elapsed,
        }
        rows.append(row)
        print(
            f"[{'TESLİM' if row['verdict'] else 'RED'}] {elapsed}s · {task[:50]} · "
            f"{delta.changed} dosya · kabul={'geçti' if accepted else 'düştü/yok'}"
        )

    delivered = sum(1 for row in rows if row["verdict"])
    output = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model": settings.model,
        "sandbox": str(sandbox),
        "rows": rows,
        "summary": {
            "tasks": len(rows),
            "delivered": delivered,
            "zero_change_routed": sum(
                1 for row in rows if row["worker_success"] and row["changed_files"] == 0
            ),
        },
    }
    destination = ROOT / "quality" / "evidence" / "sandbox-trial.json"
    destination.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"\nteslim: {delivered}/{len(rows)} · sıfır değişiklikle 'başarılı' görünen: "
        f"{output['summary']['zero_change_routed']}"
    )
    print(f"kayıt: {destination}")
    return 0 if delivered == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
