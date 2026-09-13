from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def style_prompt(series: dict[str, Any]) -> str:
    visual = series.get("visual_style", {})
    return visual.get(
        "master_prompt",
        "high-quality 2D children's cartoon, clean line art, expressive face, appealing proportions, consistent character design, production-ready animation asset, plain transparent background",
    )


def character_prompt(char: dict[str, Any], style: str, view: str, action: str = "idle") -> str:
    personality = char.get("personality", "friendly")
    role = char.get("role", "recurring character")
    return (
        f"{style}. Character: {char['name']} ({char['id']}). Role: {role}. "
        f"Personality: {personality}. View: {view}. Pose/action: {action}. "
        "Keep face, hairstyle, clothing, colors, body proportions and accessories identical across all outputs. "
        "Full body centered, no text, no watermark, transparent or plain background."
    )


def call_comfy(prompt: str, out_path: Path) -> bool:
    endpoint = os.getenv("CHARACTER_COMFY_ENDPOINT", "").strip()
    api_key = os.getenv("RUNPOD_API_KEY", "").strip()
    if not endpoint:
        return False
    payload = {
        "input": {
            "positive_prompt": prompt,
            "negative_prompt": "photorealistic, realistic skin, extra fingers, deformed face, inconsistent clothes, text, watermark",
            "width": 1024,
            "height": 1024,
            "steps": 28,
            "wait": True,
            "return_output_base64": False,
        }
    }
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    with httpx.Client(timeout=600) as client:
        r = client.post(endpoint, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    (out_path.with_suffix(".request.json")).write_text(json.dumps({"prompt": prompt, "response": data}, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def main() -> None:
    cfg = load_yaml(ROOT / "config" / "series.yaml")
    assets = load_yaml(ROOT / "config" / "assets.yaml")
    style = style_prompt(cfg.get("series", {}))
    required_views = assets["asset_contract"]["required_views"]
    required_actions = assets["asset_contract"]["required_actions"]

    manifests = []
    for char in cfg.get("characters", []):
        cid = char["id"]
        cdir = ROOT / "assets" / "characters" / cid
        requests = []
        for view in required_views:
            prompt = character_prompt(char, style, view, "idle")
            target = cdir / "poses" / f"idle_{view}.png"
            requests.append({"target": str(target.relative_to(ROOT)), "prompt": prompt, "submitted": call_comfy(prompt, target)})
        for action in required_actions:
            if action == "idle":
                continue
            prompt = character_prompt(char, style, "front", action)
            target = cdir / "poses" / f"{action}_front.png"
            requests.append({"target": str(target.relative_to(ROOT)), "prompt": prompt, "submitted": call_comfy(prompt, target)})
        manifests.append({"character_id": cid, "requests": requests})

    out = ROOT / "output" / "character_asset_requests.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifests, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "characters": len(manifests), "manifest": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
