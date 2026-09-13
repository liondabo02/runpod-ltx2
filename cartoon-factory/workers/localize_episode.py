from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from orchestrator.main import ROOT, llm_chat, extract_json

LANG_CFG = ROOT / "config" / "languages.yaml"


def enabled_languages() -> list[dict[str, str]]:
    cfg = yaml.safe_load(LANG_CFG.read_text(encoding="utf-8"))
    return [x for x in cfg["languages"] if x.get("enabled", False)]


def localize_episode(master: dict[str, Any], language: dict[str, str]) -> dict[str, Any]:
    code = language["code"]
    if code == "tr":
        out = deepcopy(master)
        out["language"] = "tr"
        return out

    compact = {
        "title": master.get("title"),
        "lesson": master.get("lesson"),
        "logline": master.get("logline"),
        "scenes": [
            {
                "id": s.get("id"),
                "duration_seconds": s.get("duration_seconds"),
                "dialogue": s.get("dialogue", []),
            }
            for s in master.get("scenes", [])
        ],
    }

    system = f"""You are a professional children's-cartoon localization director.
Translate/adapt the supplied Turkish episode into {language['name']} ({code}).
Return ONLY valid JSON with the exact same object structure, scene ids, character_ids, dialogue item count and scene durations.
Do NOT translate character ids or names. Preserve meaning, humor and age appropriateness.
Adapt dialogue length to fit the existing scene duration; natural dubbing timing is more important than literal translation.
Do not add or remove scenes. Do not alter visual action. Translate title, lesson, logline and only dialogue text.
"""
    raw = llm_chat([
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(compact, ensure_ascii=False)},
    ], temperature=0.25)
    localized = extract_json(raw)

    out = deepcopy(master)
    out["language"] = code
    out["title"] = localized.get("title", out.get("title"))
    out["lesson"] = localized.get("lesson", out.get("lesson"))
    out["logline"] = localized.get("logline", out.get("logline"))
    by_id = {str(s["id"]): s for s in localized.get("scenes", [])}
    for scene in out.get("scenes", []):
        loc = by_id.get(str(scene.get("id")))
        if not loc:
            continue
        loc_dialogue = loc.get("dialogue", [])
        src_dialogue = scene.get("dialogue", [])
        for i, line in enumerate(src_dialogue):
            if i < len(loc_dialogue):
                line["text"] = loc_dialogue[i].get("text", line.get("text", ""))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("episode_id")
    ap.add_argument("--languages", default="all", help="all or comma-separated codes, e.g. tr,de,ar")
    args = ap.parse_args()

    episode_dir = ROOT / "output" / args.episode_id
    master_path = episode_dir / "episode.json"
    master = json.loads(master_path.read_text(encoding="utf-8"))
    langs = enabled_languages()
    if args.languages != "all":
        wanted = {x.strip() for x in args.languages.split(",") if x.strip()}
        langs = [x for x in langs if x["code"] in wanted]

    outputs = {}
    for lang in langs:
        localized = localize_episode(master, lang)
        path = episode_dir / f"episode_{lang['code']}.json"
        path.write_text(json.dumps(localized, ensure_ascii=False, indent=2), encoding="utf-8")
        outputs[lang["code"]] = str(path)

    bundle = {"episode_id": args.episode_id, "languages": outputs}
    (episode_dir / "localization_manifest.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"ok": True, **bundle}, ensure_ascii=False))


if __name__ == "__main__":
    main()
