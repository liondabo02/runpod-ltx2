"""S01E001 v2 doğrulayıcı: süre, kronoloji, açılış tutarlılığı, Kaan dili, ses haritası."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "studio" / "s01e001"
EPISODE = BASE / "episode-v2.json"
OPENING = BASE / "episode-open-30s-v2.json"
V1 = BASE / "episode.json"
PILOT = ROOT / "workflows" / "S01E001-pilot-30s-plan.json"
KAAN_LEXICON = {"Kuş!", "Aa!", "Mavi!", "Ya!"}
KAAN_ACTIONS = {"blinks", "wobbles", "laughs", "touches", "watches", "claps", "giggles",
                "points", "gasps", "surprised", "looks_up", "waddles", "helps_lid",
                "looks_around", "looks", "pulls", "places", "hands_strip", "pushes",
                "sneezes", "blows", "counts", "sits", "reaches", "offers"}
ORDER = ["tail_attach_start", "tail_attached", "launch_1", "tail_snaps",
         "search_tail", "repair_try_1", "repair_done", "launch_2"]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(episode: dict, opening: dict) -> list[str]:
    problems: list[str] = []
    scenes = episode.get("scenes") or []
    total = sum(int(s.get("duration_seconds", 0)) for s in scenes)
    if total != 480:
        problems.append(f"bölüm süresi {total} != 480")
    cursor = 0
    for scene in scenes:
        if int(scene.get("start_seconds", -1)) != cursor:
            problems.append(f"{scene.get('scene_id')} başlangıcı hatalı")
        cursor += int(scene.get("duration_seconds", 0))
        beats = scene.get("beats") or []
        beat_total = sum(int(b.get("duration_seconds", 0)) for b in beats)
        if beat_total != int(scene.get("duration_seconds", 0)):
            problems.append(f"{scene.get('scene_id')} beat toplamı {beat_total} != {scene['duration_seconds']}")
        for beat in beats:
            duration = int(beat.get("duration_seconds", 0))
            if not 5 <= duration <= 10:
                problems.append(f"{scene.get('scene_id')} beat {duration} sn (5-10 dışı)")
            if not beat.get("action") or not beat.get("focus"):
                problems.append(f"{scene.get('scene_id')} beat eksik alan")
    if cursor != 480:
        problems.append(f"sahne bitişi {cursor} != 480")

    cast = {row["character_id"]: row for row in episode.get("cast") or []}
    if set(cast) != {"aden", "kaan", "esra"}:
        problems.append(f"cast beklenenden farklı: {sorted(cast)}")
    if cast.get("aden", {}).get("gender") != "female" or cast.get("aden", {}).get("age_years") != 3:
        problems.append("Aden kız/3 yaş değil")
    if cast.get("kaan", {}).get("gender") != "male" or cast.get("kaan", {}).get("age_years") != 1:
        problems.append("Kaan erkek/1 yaş değil")

    location = episode.get("location_plan") or {}
    if location.get("locations") != ["park"] or location.get("time_of_day") != "sabah":
        problems.append("mekân/zaman tek park + sabah değil")

    for scene in scenes:
        for beat in scene.get("beats") or []:
            action = beat.get("kaan_action")
            if action not in KAAN_ACTIONS:
                problems.append(f"{scene.get('scene_id')} Kaan eylemi güvenli listede değil: {action}")

    for scene in scenes:
        for line in scene.get("dialogue") or []:
            if line.get("speaker") not in cast:
                problems.append(f"{scene.get('scene_id')} bilinmeyen konuşmacı")
            if line.get("speaker") == "kaan" and line.get("text") not in KAAN_LEXICON:
                problems.append(f"{scene.get('scene_id')} Kaan sözlük dışı: {line.get('text')!r}")
            if not line.get("emotion"):
                problems.append(f"{scene.get('scene_id')} replikte duygu yok")
            duration = float(line.get("voice_duration_seconds", 0))
            if not 0.5 <= duration <= 4:
                problems.append(f"{scene.get('scene_id')} ses süresi {duration} (0.5-4 dışı)")
            start = float(line.get("start_seconds", -1))
            if not (scene["start_seconds"] <= start < scene["start_seconds"] + scene["duration_seconds"]):
                problems.append(f"{scene.get('scene_id')} replik zaman kodu sahne dışında")

    event_scene = {row["event"]: row["scene_id"] for row in episode.get("events") or []}
    if list(event_scene) != ORDER:
        problems.append(f"olay sırası hatalı: {list(event_scene)}")
    indices = {scene["scene_id"]: index for index, scene in enumerate(scenes)}
    sequence = [indices.get(event_scene[name], -1) for name in ORDER]
    if sequence != sorted(sequence) or -1 in sequence:
        problems.append(f"olay kronolojisi sahne sırasıyla uyumsuz: {sequence}")

    shots = opening.get("shots") or []
    shot_total = sum(int(s.get("duration_seconds", 0)) for s in shots)
    if shot_total != 30 or len(shots) != 6:
        problems.append(f"açılış {len(shots)} çekim / {shot_total} sn")
    cursor = 0
    for shot in shots:
        if int(shot.get("start_seconds", -1)) != cursor:
            problems.append(f"{shot.get('shot_id')} başlangıcı hatalı")
        cursor += int(shot.get("duration_seconds", 0))
        for field in ("camera", "positions", "action", "sound", "continuity", "safety"):
            if not shot.get(field):
                problems.append(f"{shot.get('shot_id')} {field} eksik")

    first_events = [beat.get("event") for beat in scenes[0].get("beats", [])[:3]]
    open_events = [shot.get("event") for shot in shots]
    dedup = [name for index, name in enumerate(open_events) if index == 0 or name != open_events[index - 1]]
    if dedup != first_events:
        problems.append(f"açılış olayları S01 ile uyuşmuyor: {dedup} != {first_events}")
    for shot in shots:
        if shot.get("source_scene") != "V2-S01" or shot.get("source_beat") not in (0, 1, 2):
            problems.append(f"{shot.get('shot_id')} kaynak sahne/beat hatalı")

    harun = episode.get("harun") or {}
    if harun.get("canon_role") != "uncle_of (dayı)":
        problems.append("Harun kanon rolü doğrulanmamış")

    if episode.get("status") != "DRAFT_FOR_OWNER_APPROVAL" or not episode.get("not_final"):
        problems.append("v2 taslak/not_final değil")
    if opening.get("status") != "DRAFT_FOR_OWNER_APPROVAL" or not opening.get("not_final"):
        problems.append("açılış taslak/not_final değil")

    v1 = _load(V1)
    if len(v1.get("scenes") or []) != 12 or sum(s["duration_seconds"] for s in v1["scenes"]) != 480:
        problems.append("v1 dosyası korunmamış")
    pilot = _load(PILOT)
    if pilot.get("status") != "PROPOSED_NOT_OWNER_APPROVED" or pilot.get("target_duration_seconds") != 30:
        problems.append("bağımsız POC dosyası değişmiş")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    episode, opening = _load(EPISODE), _load(OPENING)
    problems = validate(episode, opening)
    result = {"episode_seconds": sum(s["duration_seconds"] for s in episode["scenes"]),
              "opening_seconds": sum(s["duration_seconds"] for s in opening["shots"]),
              "scenes": len(episode["scenes"]), "shots": len(opening["shots"]),
              "problems": problems, "ok": not problems}
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else
          ("PASS" if not problems else "FAIL: " + "; ".join(problems)))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
