"""Produce step backed by the cloud outbox.

Instead of calling a model inside a mission (slow on a 12 GB ARM VM, and rate
limited on free endpoints), the worker consumes a patch proposal the cloud
worker already produced. The proposal is applied strictly: path checks, exact
find/replace, a real content change, the project's own acceptance gate, and the
emergency stop file. Consumed proposals are archived.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .outbox import apply_proposal, command_verify, load_proposals

DEFAULT_GATE = "python tools/check_offline.py"


def _score(proposal: dict, objective: str) -> int:
    title = str(proposal.get("task") or "").casefold()
    wanted = objective.casefold()
    if not title:
        return 0
    if title == wanted:
        return 100
    if title in wanted or wanted in title:
        return 60
    overlap = len(set(title.split()) & set(wanted.split()))
    return min(50, overlap * 5)


def make_outbox_executor(
    project_root: str | Path,
    outbox_dir: str | Path,
    *,
    stop_file: str | Path | None = None,
    gate_command: str = DEFAULT_GATE,
):
    """Return a WorkerExecutor that applies one pending proposal per task."""

    root = Path(project_root)
    outbox = Path(outbox_dir)
    applied_dir = outbox / "applied"

    def _execute(item, worker_id):
        from .worker_runtime import WorkerExecutionResult

        step = str(item.task_id).rsplit(":", 1)[-1]
        if step != "produce":
            return WorkerExecutionResult(
                task_id=item.task_id,
                worker_id=worker_id,
                success=True,
                summary=f"{step}: bulut hattı yalnız üretimde kullanılır",
            )
        if stop_file is not None and Path(stop_file).exists():
            return WorkerExecutionResult(
                task_id=item.task_id,
                worker_id=worker_id,
                success=False,
                summary="acil durdurma: bulut önerisi uygulanmadı",
            )

        pending = [row for row in load_proposals(outbox) if row.get("edits")]
        if not pending:
            return WorkerExecutionResult(
                task_id=item.task_id,
                worker_id=worker_id,
                success=False,
                summary="teslimat yok: outbox'ta uygun öneri yok",
            )
        pending.sort(key=lambda row: _score(row, str(getattr(item, "title", ""))), reverse=True)
        proposal = pending[0]

        gate = root / "tools" / "check_offline.py"
        verify = command_verify(gate_command) if gate.is_file() else None
        outcome = apply_proposal(
            proposal,
            root,
            verify,
            require_acceptance=True,
            stop_file=stop_file,
        )
        files = outcome.get("files") or []
        if outcome["status"] == "applied":
            applied_dir.mkdir(parents=True, exist_ok=True)
            source = Path(proposal.get("_file", ""))
            if source.is_file():
                shutil.move(str(source), str(applied_dir / source.name))
            return WorkerExecutionResult(
                task_id=item.task_id,
                worker_id=worker_id,
                success=True,
                summary=(
                    f"{len(files)} dosya değişti; kabul kapısı geçti; $0.0000 "
                    f"(bulut önerisi: {proposal.get('id', '')})"
                ),
                artifacts=tuple(str(root / name) for name in files),
            )
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=False,
            summary=f"bulut önerisi reddedildi: {outcome.get('reason', '')}",
        )

    return _execute
