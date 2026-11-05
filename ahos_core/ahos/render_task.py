"""Explicit, local ComfyUI render executor; empty outputs never count as success."""
from pathlib import Path
from .comfy_bridge import ComfyUnavailable, DEFAULT_HOST, fill_template, render
from .worker_runtime import WorkerExecutionResult

def make_render_executor(workflow_path, out_dir):
    def executor(item, worker_id):
        objective = str(getattr(item, "objective", getattr(item, "title", "")))
        prompt = objective.removeprefix("render:").strip()[:400]
        if not prompt:
            return WorkerExecutionResult(
                item.task_id, worker_id, False, "Render başarısız: boş prompt",
            )
        try:
            workflow = fill_template(workflow_path, prompt=prompt)
            paths = render(workflow, out_dir)
            root = Path(out_dir).resolve()
            artifacts = tuple(str(Path(p)) for p in paths
                if Path(p).suffix.lower() in {".png", ".mp4"}
                and not Path(p).is_symlink()
                and Path(p).is_file() and Path(p).stat().st_size > 0
                and Path(p).resolve().is_relative_to(root))
            return WorkerExecutionResult(item.task_id, worker_id, bool(artifacts),
                f"{len(artifacts)} dosya üretildi", artifacts=artifacts)
        except ComfyUnavailable:
            return WorkerExecutionResult(item.task_id, worker_id, False,
                f"ComfyUI kapalı: {DEFAULT_HOST}")
        except (OSError, ValueError, KeyError, RuntimeError, TimeoutError) as exc:
            return WorkerExecutionResult(item.task_id, worker_id, False,
                f"Render başarısız: {exc}")
    return executor
