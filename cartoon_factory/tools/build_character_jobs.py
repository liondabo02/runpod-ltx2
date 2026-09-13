from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    prompts = load_yaml(ROOT / "config" / "character_prompts.yaml")
    assets = load_yaml(ROOT / "config" / "assets.yaml")
    style = prompts["style_lock"]
    contract = assets["asset_contract"]
    jobs: list[dict[str, Any]] = []

    for char_id, char in prompts["characters"].items():
        palette = next((c["palette"] for c in assets["characters"] if c["id"] == char_id), [])
        base = f"{style['positive']}. Character: {char['description']}. Signature: {char['signature']}. Palette: {', '.join(palette)}."
        ref_dir = f"assets/characters/{char_id}"

        jobs.append({
            "job_id": f"{char_id}-master-front",
            "character_id": char_id,
            "kind": "master_reference",
            "view": "front",
            "prompt": base + " Front view, neutral standing pose, symmetrical model sheet, feet visible.",
            "negative_prompt": style["negative"],
            "output": f"{ref_dir}/reference/front.png",
            "requires_reference": False,
        })

        for view in contract["required_views"]:
            if view == "front":
                continue
            jobs.append({
                "job_id": f"{char_id}-view-{view}",
                "character_id": char_id,
                "kind": "view",
                "view": view,
                "prompt": base + f" Exact same character, {view} view, neutral standing pose, feet visible.",
                "negative_prompt": style["negative"],
                "output": f"{ref_dir}/reference/{view}.png",
                "requires_reference": True,
                "reference": f"{ref_dir}/reference/front.png",
            })

        for emotion in contract["required_emotions"]:
            jobs.append({
                "job_id": f"{char_id}-emotion-{emotion}",
                "character_id": char_id,
                "kind": "emotion",
                "emotion": emotion,
                "prompt": base + f" Portrait face layer, exact same character, {emotion} expression, transparent background.",
                "negative_prompt": style["negative"],
                "output": f"{ref_dir}/faces/{emotion}.png",
                "requires_reference": True,
                "reference": f"{ref_dir}/reference/front.png",
            })

        for action in contract["required_actions"]:
            jobs.append({
                "job_id": f"{char_id}-pose-{action}",
                "character_id": char_id,
                "kind": "pose",
                "action": action,
                "prompt": base + f" Full-body animation key pose: {action}, three-quarter view, exact same clothing and proportions, transparent background.",
                "negative_prompt": style["negative"],
                "output": f"{ref_dir}/poses/{action}_three_quarter.png",
                "requires_reference": True,
                "reference": f"{ref_dir}/reference/front.png",
            })

    out = ROOT / "output" / "character_jobs.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "jobs": len(jobs), "output": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
