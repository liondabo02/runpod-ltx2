from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    assets_cfg = yaml.safe_load((ROOT / "config" / "assets.yaml").read_text(encoding="utf-8"))
    required_actions = assets_cfg["asset_contract"]["required_actions"]
    required_views = assets_cfg["asset_contract"]["required_views"]
    required_emotions = assets_cfg["asset_contract"]["required_emotions"]
    required_mouths = assets_cfg["asset_contract"]["mouth_shapes"]

    report = {"characters": {}, "ready": True}
    for char in assets_cfg.get("characters", []):
        cid = char["id"]
        base = ROOT / "assets" / "characters" / cid
        missing = []
        for view in required_views:
            p = base / "poses" / f"idle_{view}.png"
            if not p.exists():
                missing.append(str(p.relative_to(ROOT)))
        for action in required_actions:
            p = base / "poses" / f"{action}_front.png"
            if not p.exists():
                missing.append(str(p.relative_to(ROOT)))
        for emotion in required_emotions:
            p = base / "faces" / f"{emotion}.png"
            if not p.exists():
                missing.append(str(p.relative_to(ROOT)))
        for mouth in required_mouths:
            p = base / "mouths" / f"{mouth}.png"
            if not p.exists():
                missing.append(str(p.relative_to(ROOT)))
        voice = ROOT / "assets" / "voices" / f"{cid}.onnx"
        if not voice.exists():
            missing.append(str(voice.relative_to(ROOT)))

        ready = len(missing) == 0
        report["characters"][cid] = {"ready": ready, "missing": missing}
        report["ready"] = report["ready"] and ready

    episode_id = os.getenv("EPISODE_ID")
    if episode_id:
        ep = ROOT / "output" / episode_id
        final = ep / f"{episode_id}.mp4"
        report["episode"] = {
            "id": episode_id,
            "final_exists": final.exists(),
            "final_path": str(final),
        }
        report["ready"] = report["ready"] and final.exists()

    out = ROOT / "output" / "qc_visual.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(0 if report["ready"] else 2)


if __name__ == "__main__":
    main()
