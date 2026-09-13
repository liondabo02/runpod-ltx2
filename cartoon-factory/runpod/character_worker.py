from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any

import requests

COMFY_URL = os.getenv("COMFYUI_API_URL", "http://127.0.0.1:8188").rstrip("/")
WORKFLOW = Path(os.getenv("CHARACTER_WORKFLOW", "/app/workflows/character_t2i.api.json"))
TIMEOUT = int(os.getenv("CHARACTER_JOB_TIMEOUT", "900"))


def _load_workflow() -> dict[str, Any]:
    if not WORKFLOW.exists():
        raise FileNotFoundError(f"Missing workflow: {WORKFLOW}")
    return json.loads(WORKFLOW.read_text(encoding="utf-8"))


def _inject(workflow: dict[str, Any], positive: str, negative: str, seed: int) -> dict[str, Any]:
    graph = json.loads(json.dumps(workflow))
    for node in graph.values():
        if not isinstance(node, dict):
            continue
        cls = str(node.get("class_type", ""))
        inputs = node.setdefault("inputs", {})
        title = str((node.get("_meta") or {}).get("title", "")).lower()
        if cls in {"CLIPTextEncode", "CLIPTextEncodeSDXL"}:
            if "negative" in title:
                inputs["text"] = negative
            elif "positive" in title or "prompt" in title:
                inputs["text"] = positive
        if cls in {"KSampler", "KSamplerAdvanced", "RandomNoise"}:
            if "seed" in inputs:
                inputs["seed"] = seed
            if "noise_seed" in inputs:
                inputs["noise_seed"] = seed
    return graph


def _queue(prompt: dict[str, Any]) -> str:
    r = requests.post(f"{COMFY_URL}/prompt", json={"prompt": prompt}, timeout=30)
    r.raise_for_status()
    return r.json()["prompt_id"]


def _wait(prompt_id: str) -> dict[str, Any]:
    deadline = time.time() + TIMEOUT
    while time.time() < deadline:
        r = requests.get(f"{COMFY_URL}/history/{prompt_id}", timeout=30)
        r.raise_for_status()
        payload = r.json()
        if prompt_id in payload:
            return payload[prompt_id]
        time.sleep(2)
    raise TimeoutError(f"ComfyUI job timed out: {prompt_id}")


def _first_image(history: dict[str, Any]) -> tuple[str, str, str]:
    for output in (history.get("outputs") or {}).values():
        for image in output.get("images", []) if isinstance(output, dict) else []:
            return image["filename"], image.get("subfolder", ""), image.get("type", "output")
    raise RuntimeError("No image output found")


def _download(filename: str, subfolder: str, kind: str) -> bytes:
    r = requests.get(
        f"{COMFY_URL}/view",
        params={"filename": filename, "subfolder": subfolder, "type": kind},
        timeout=120,
    )
    r.raise_for_status()
    return r.content


def handler(job: dict[str, Any]) -> dict[str, Any]:
    inp = job.get("input") or {}
    positive = str(inp.get("positive_prompt") or "").strip()
    negative = str(inp.get("negative_prompt") or "").strip()
    seed = int(inp.get("seed", 1))
    if not positive:
        return {"error": "positive_prompt is required"}
    workflow = _inject(_load_workflow(), positive, negative, seed)
    prompt_id = _queue(workflow)
    history = _wait(prompt_id)
    filename, subfolder, kind = _first_image(history)
    data = _download(filename, subfolder, kind)
    return {
        "ok": True,
        "prompt_id": prompt_id,
        "filename": filename,
        "image_base64": base64.b64encode(data).decode("ascii"),
    }


if __name__ == "__main__":
    try:
        import runpod
    except ImportError as exc:
        raise SystemExit("Install runpod to start the serverless worker") from exc
    runpod.serverless.start({"handler": handler})
