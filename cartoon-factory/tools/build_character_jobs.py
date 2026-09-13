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
    asset_by_id = {c["id"]: c for c in assets["characters"]}
    jobs: list[dict[str, Any]] = []

    for char_id, char in prompts["characters"].items():
        meta = asset_by_id.get(char_id, {})
        palette = meta.get("apparel_palette", [])
        acting = char.get("acting_notes", "")
        base = (
            f"{style['positive']}. Character: {char['description']}. "
            f"Signature: {char['signature']}. Apparel palette: {', '.join(palette)}. "
            f"Acting language: {acting}."
        )
        ref_dir = f"assets/characters/{char_id}"

        jobs.append({
            "job_id": f"{char_id}-master-front",
            "character_id": char_id,
            "kind": "master_reference",
            "view": "front",
            "prompt": base + " Front view, neutral standing pose, clean production model sheet, full body, feet visible.",
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
                "prompt": base + f" Exact same approved character, {view} view, neutral standing pose, full body, feet visible.",
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
                "prompt": base + f" Face layer, exact same approved character, {emotion} expression, transparent background.",
                "negative_prompt": style["negative"],
                "output": f"{ref_dir}/faces/{emotion}.png",
                "requires_reference": True,
                "reference": f"{ref_dir}/reference/front.png",
            })

        # Front pose is mandatory because the sprite renderer uses it directly.
        for action in contract["required_actions"]:
            for view in ["front", "three_quarter"]:
                jobs.append({
                    "job_id": f"{char_id}-pose-{action}-{view}",
                    "character_id": char_id,
                    "kind": "pose",
                    "action": action,
                    "view": view,
                    "prompt": base + f" Full-body animation key pose: {action}, {view} view, exact same approved character, clothing and proportions, transparent background.",
                    "negative_prompt": style["negative"],
                    "output": f"{ref_dir}/poses/{action}_{view}.png",
                    "requires_reference": True,
                    "reference": f"{ref_dir}/reference/front.png",
                })

        for shape in contract["mouth_shapes"]:
            jobs.append({
                "job_id": f"{char_id}-mouth-{shape}",
                "character_id": char_id,
                "kind": "mouth",
                "shape": shape,
                "prompt": base + f" Isolated mouth replacement layer for lip-sync shape {shape}, exact same face style, transparent background.",
                "negative_prompt": style["negative"],
                "output": f"{ref_dir}/mouths/{shape}.png",
                "requires_reference": True,
                "reference": f"{ref_dir}/reference/front.png",
            })

    out = ROOT / "output" / "character_jobs.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "characters": len(prompts['characters']), "jobs": len(jobs), "output": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
