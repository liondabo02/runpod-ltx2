"""Explicit, local ComfyUI render executor; empty outputs never count as success."""
from pathlib import Path
from .comfy_bridge import ComfyUnavailable, DEFAULT_HOST, fill_template, render
from .worker_runtime import WorkerExecutionResult

_VIDEO_OUTPUT_NODES = {"SaveVideo", "VHS_VideoCombine"}


def _valid_artifact(candidate, root: Path, *, video_required: bool) -> bool:
    """Reject empty, spoofed or escaped media files before reporting delivery."""
    path = Path(candidate)
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        return False
    suffix = path.suffix.lower()
    if suffix not in ({".mp4"} if video_required else {".png", ".mp4"}):
        return False
    if path.stat().st_size < 12:
        return False
    with path.open("rb") as stream:
        header = stream.read(12)
    if suffix == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    return header[4:8] == b"ftyp"


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
            video_nodes = any(
                isinstance(node, dict) and node.get("class_type") in _VIDEO_OUTPUT_NODES
                for node in workflow.values()
            )
            video_required = video_nodes or "text2video" in Path(workflow_path).stem.lower()
            if video_required and not video_nodes:
                return WorkerExecutionResult(
                    item.task_id, worker_id, False,
                    "Gerçek video workflow'u yok: SaveVideo veya VideoCombine çıkışı gerekli",
                )
            paths = render(workflow, out_dir)
            root = Path(out_dir).resolve()
            artifacts = tuple(str(Path(p)) for p in paths
                if _valid_artifact(p, root, video_required=video_required))
            return WorkerExecutionResult(item.task_id, worker_id, bool(artifacts),
                f"{len(artifacts)} dosya üretildi", artifacts=artifacts)
        except ComfyUnavailable:
            return WorkerExecutionResult(item.task_id, worker_id, False,
                f"ComfyUI kapalı: {DEFAULT_HOST}")
        except (OSError, ValueError, KeyError, RuntimeError, TimeoutError) as exc:
            return WorkerExecutionResult(item.task_id, worker_id, False,
                f"Render başarısız: {exc}")
    return executor
