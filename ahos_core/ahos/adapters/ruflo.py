"""AHOS ↔ Ruflo bridge.

Ruflo (Claude-Flow 3.x) is an external Node CLI. AHOS treats it as one more
*worker executor*: give it a mission, enforce a wall-clock limit, record what
changed on disk, and never let it spend money silently.

Design rules
------------
* Only local/tunnelled models: the child process gets ``OLLAMA``-style env that
  points at AHOS' free endpoint and every paid-provider variable is stripped.
* Bounded: subprocess timeout + process-tree kill on expiry.
* Evidence-based: success requires a real file change under the project root.
* Auditable: stdout/stderr tail is written to the artifacts directory.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from ..code_work import diff_snapshots, snapshot


@dataclass(frozen=True)
class RufloConfig:
    node: str
    cli: str
    timeout_seconds: float = 180.0
    model: str = "qwen2.5-coder:7b"
    base_url: str = "http://127.0.0.1:11500"
    command_template: str = "{node} {cli} task run --prompt {prompt}"
    #: ``plan``  → Ruflo yalnız görev/plan üretir, yürütmeyi AHOS yapar (ücretsiz).
    #: ``execute``→ Ruflo swarm çalıştırır; Claude Code ücretli olabileceği için
    #:             ``AHOS_ALLOW_PAID_LLM=1`` olmadan reddedilir.
    mode: str = "execute"


def _project_env(base_url: str, model: str) -> dict[str, str]:
    """Environment for the child: free local model, no paid keys inherited."""

    env = {
        key: value
        for key, value in os.environ.items()
        if "API_KEY" not in key and "ANTHROPIC" not in key and "OPENAI" not in key
    }
    env.update(
        {
            "OLLAMA_BASE_URL": base_url,
            "OLLAMA_HOST": base_url,
            "AHOS_LLM_BASE_URL": f"{base_url}/v1",
            "AHOS_LLM_MODEL": model,
            "AHOS_LLM_FREE": "1",
            "AHOS_ALLOW_PAID_LLM": "0",
            "CI": "1",
            "NO_COLOR": "1",
            "DO_NOT_TRACK": "1",
            "CLAUDE_FLOW_TELEMETRY": "0",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        }
    )
    return env


def _kill_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
        )
    else:  # pragma: no cover - posix
        try:
            os.killpg(os.getpgid(pid), 15)
        except OSError:
            pass


def make_ruflo_executor(
    project_root: str | Path,
    artifacts_root: str | Path,
    *,
    config: RufloConfig,
):
    """Return a ``WorkerExecutor`` compatible callable."""

    root = Path(project_root).resolve()
    artifacts = Path(artifacts_root).resolve()
    artifacts.mkdir(parents=True, exist_ok=True)

    def run_mission(item, worker_id: str):
        from ..worker_runtime import WorkerExecutionResult

        mission_file = artifacts / f"ruflo-{item.task_id.replace(':', '_')[:80]}.log"
        before = snapshot(root)
        started = time.time()

        argv = config.command_template.format(
            node=config.node,
            cli=config.cli,
            prompt=json.dumps(item.title or item.task_id),
            root=str(root),
            mission=item.task_id,
        )
        log_handle = mission_file.open("wb")
        try:
            process = subprocess.Popen(
                argv,
                shell=isinstance(argv, str),
                cwd=str(root),
                env=_project_env(config.base_url, config.model),
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
                ),
            )
        except (OSError, ValueError) as exc:
            log_handle.close()
            return WorkerExecutionResult(
                task_id=item.task_id,
                worker_id=worker_id,
                success=False,
                summary=f"ruflo başlatılamadı: {exc}",
                artifacts=(),
            )
        try:
            exit_code = process.wait(timeout=config.timeout_seconds)
        except subprocess.TimeoutExpired:
            _kill_tree(process.pid)
            process.wait(timeout=30)
            log_handle.close()
            return WorkerExecutionResult(
                task_id=item.task_id,
                worker_id=worker_id,
                success=False,
                summary=(
                    f"ruflo zaman aşımı ({config.timeout_seconds:.0f}s); "
                    "süreç ağacı durduruldu"
                ),
                artifacts=(str(mission_file),),
            )
        finally:
            try:
                log_handle.close()
            except OSError:
                pass

        elapsed = time.time() - started
        after = snapshot(root)
        changes = diff_snapshots(root, before, after)
        changed = [row.path for row in changes] if changes else []
        tail = ""
        try:
            tail = mission_file.read_text(encoding="utf-8", errors="replace")[-600:]
        except OSError:
            pass

        if config.mode == "plan":
            # Ruflo yalnız plan/görev üretir; dosya değişikliği beklenmez ve
            # yürütme iddiası yapılmaz.
            ok = exit_code == 0
            return WorkerExecutionResult(
                task_id=item.task_id,
                worker_id=worker_id,
                success=ok,
                summary=(
                    "ruflo planı oluşturuldu (yürütme AHOS'ta): "
                    + (tail.strip().splitlines()[-1][:160] if tail.strip() else "ok")
                )
                if ok
                else f"ruflo plan hatası (kod {exit_code}): {tail.strip()[:160]}",
                artifacts=(str(mission_file),),
            )

        if config.mode == "execute" and os.environ.get(
            "AHOS_ALLOW_PAID_LLM", ""
        ).strip().lower() not in {"1", "true", "yes", "on"}:
            return WorkerExecutionResult(
                task_id=item.task_id,
                worker_id=worker_id,
                success=False,
                summary=(
                    "ruflo swarm yürütmesi Claude Code (ücretli) çağırır; "
                    "AHOS_ALLOW_PAID_LLM=1 olmadan reddedildi"
                ),
                artifacts=(str(mission_file),),
            )

        # Dosya değişikliği TEK BAŞINA doğrulama sayılmaz. Bağımsız kabul
        # paketi (kalite kapısı + node --check / py_compile) çalıştırılır.
        from ..acceptance_suite import run_acceptance

        acceptance = run_acceptance(root, changed, timeout=60.0)
        acceptance_ok, acceptance_summary = acceptance.ok, acceptance.summary

        if exit_code != 0:
            success = False
            summary = f"ruflo hata kodu {exit_code}: {tail.strip()[:180]}"
        elif not changed:
            success = False
            summary = "ruflo çalıştı ama dosya değişmedi (teslim yok)"
        elif not acceptance_ok:
            success = False
            summary = (
                f"{len(changed)} dosya değişti; bağımsız kabul BAŞARISIZ: "
                f"{acceptance_summary[:160]}"
            )
        else:
            success = True
            summary = (
                f"{len(changed)} dosya değişti; bağımsız kabul geçti "
                f"({acceptance_summary[:80]}); $0.0000; ruflo {elapsed:.1f}s"
            )

        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=success,
            summary=summary,
            artifacts=(str(mission_file),),
        )

    return run_mission


def _run_acceptance(root: Path, *, timeout: float = 90.0) -> tuple[bool, str]:
    """Run the project's own quality gate (hash-pinned by ``acceptance``)."""

    gate = root / "tools" / "check_offline.py"
    if not gate.is_file():
        return False, "kabul komutu yok (tools/check_offline.py)"

    import sys

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        completed = subprocess.run(
            [sys.executable, str(gate)],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"kabul çalıştırılamadı: {exc}"

    detail = (completed.stdout or completed.stderr or "").strip().splitlines()
    last = detail[-1][:160] if detail else ""
    return completed.returncode == 0, last or f"exit {completed.returncode}"
