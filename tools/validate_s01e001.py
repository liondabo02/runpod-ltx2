"""S01E001 paket doğrulayıcı: süre, karakter, diyalog ve çekim listesi.

Kullanım:
    python tools/validate_s01e001.py [--json]
Çıkış: 0 = tüm kontroller geçti, 1 = ihlal var.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
EPISODE = ROOT / "studio" / "s01e001" / "episode.json"
SHOTS = ROOT / "studio" / "s01e001" / "shotlist-30s.json"
TARGET = 480
SHOT_TARGET = 30


def _words(text: str) -> list[str]:
    return [part for part in re.split(r"\s+", text.strip()) if part]


def validate(episode: dict, shots: dict) -> list[str]:
    problems: list[str] = []

    scenes = episode.get("scenes") or []
    total = sum(int(scene.get("duration_seconds", 0)) for scene in scenes)
    if total != TARGET:
        problems.append(f"bölüm süresi {total} != {TARGET}")
    if not scenes:
        problems.append("sahne yok")
    cursor = 0
    for scene in scenes:
        if int(scene.get("start_seconds", -1)) != cursor:
            problems.append(f"{scene.get('scene_id')} başlangıcı {scene.get('start_seconds')} != {cursor}")
        cursor += int(scene.get("duration_seconds", 0))
    if cursor != TARGET:
        problems.append(f"sahne bitişi {cursor} != {TARGET}")

    cast = {item["character_id"]: item for item in episode.get("cast") or []}
    for required in ("aden", "kaan"):
        if required not in cast:
            problems.append(f"cast eksik: {required}")
    if cast.get("aden", {}).get("gender") != "female":
        problems.append("Aden kız değil")
    if int(cast.get("aden", {}).get("age_years", 0)) != 3:
        problems.append("Aden 3 yaşında değil")
    if cast.get("kaan", {}).get("gender") != "male":
        problems.append("Kaan erkek değil")
    if int(cast.get("kaan", {}).get("age_years", 0)) != 1:
        problems.append("Kaan 1 yaşında değil")

    goals = set(episode.get("learning_goals") or [])
    if goals != {"sabır", "paylaşma", "yardımlaşma"}:
        problems.append(f"öğrenme hedefleri beklenenden farklı: {sorted(goals)}")
    tags = {tag for scene in scenes for tag in scene.get("behavior_tags") or []}
    if not goals <= tags:
        problems.append(f"davranış etiketleri eksik: {sorted(goals - tags)}")

    for scene in scenes:
        for line in scene.get("dialogue") or []:
            speaker = line.get("speaker")
            text = str(line.get("text") or "")
            if speaker not in cast:
                problems.append(f"{scene.get('scene_id')}: bilinmeyen konuşmacı {speaker}")
            if speaker == "kaan" and len(_words(text)) > 2:
                problems.append(f"{scene.get('scene_id')}: Kaan çok uzun konuştu: {text!r}")
            if speaker == "kaan" and text.rstrip("!...").count(" ") > 1:
                problems.append(f"{scene.get('scene_id')}: Kaan cümle kurdu: {text!r}")

    shot_rows = shots.get("shots") or []
    shot_total = sum(int(shot.get("duration_seconds", 0)) for shot in shot_rows)
    if shot_total != SHOT_TARGET:
        problems.append(f"çekim süresi {shot_total} != {SHOT_TARGET}")
    if len(shot_rows) != 6:
        problems.append(f"çekim sayısı {len(shot_rows)} != 6")
    cursor = 0
    for shot in shot_rows:
        if int(shot.get("start_seconds", -1)) != cursor:
            problems.append(f"{shot.get('shot_id')} başlangıcı {shot.get('start_seconds')} != {cursor}")
        cursor += int(shot.get("duration_seconds", 0))
        for field in ("camera", "positions", "action", "sound", "continuity"):
            if not shot.get(field):
                problems.append(f"{shot.get('shot_id')}: {field} eksik")
    if cursor != SHOT_TARGET:
        problems.append(f"çekim bitişi {cursor} != {SHOT_TARGET}")

    if episode.get("status") != "DRAFT_FOR_OWNER_APPROVAL":
        problems.append("durum taslak değil")
    if not episode.get("not_final"):
        problems.append("not_final true değil")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    episode = json.loads(EPISODE.read_text(encoding="utf-8"))
    shots = json.loads(SHOTS.read_text(encoding="utf-8"))
    problems = validate(episode, shots)
    result = {
        "episode": str(EPISODE), "shots": str(SHOTS),
        "scenes": len(episode.get("scenes") or []),
        "episode_seconds": sum(s.get("duration_seconds", 0) for s in episode.get("scenes") or []),
        "shot_seconds": sum(s.get("duration_seconds", 0) for s in shots.get("shots") or []),
        "problems": problems, "ok": not problems,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else
          ("PASS" if not problems else "FAIL: " + "; ".join(problems)))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
