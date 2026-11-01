"""Çizgi film hattı: brief'ten bölüm üretimi (senaryo → çizim → ses → montaj → kapı).

Bu modül, departmanın "çizgi film yap" komutunu gerçek bir teslime çevirir.
Tek adam kararı: senaryo şablonla üretilir (deterministik, 0 $); model
bağlanırsa `planner` parametresiyle aynı sözleşme korunarak değiştirilebilir.
"""

from __future__ import annotations

import json
from pathlib import Path

from .studio_2d import Episode, Line, Scene, episode_timeline, render_episode
from .studio_qa import verify_episode
from .studio_voice import (
    build_track,
    list_voices,
    pick_voice,
    synthesize_wav,
    wav_duration,
)

BACKGROUNDS = ("day", "sunset", "night")


def storyboard(brief: str, *, scenes: int = 3, seconds: float = 3.0,
               cast: tuple[str, str] = ("aden", "kaan")) -> Episode:
    """Brief'ten deterministik bir sahne planı üret."""

    title = brief.strip().rstrip(".")[:70] or "Yeni Bölüm"
    first, second = cast
    plan: list[Scene] = []
    plan.append(
        Scene(
            scene_id="s1", setting="Açılış", background=BACKGROUNDS[0],
            characters=[first, second],
            lines=[
                Line("s1", first, f"Bugün {title.lower()} hakkında konuşacağız.", seconds),
                Line("s1", second, "Harika! Hemen başlayalım.", seconds),
            ],
        )
    )
    middle = max(1, scenes - 2)
    for index in range(middle):
        stage = BACKGROUNDS[(index + 1) % len(BACKGROUNDS)]
        plan.append(
            Scene(
                scene_id=f"s{index + 2}",
                setting=f"Sahne {index + 2}",
                background=stage,
                characters=[second, first],
                lines=[
                    Line(f"s{index + 2}", second, "Bunu birlikte deneyelim.", seconds),
                    Line(f"s{index + 2}", first, "Önce dikkatlice bakalım.", seconds),
                ],
            )
        )
    plan.append(
        Scene(
            scene_id=f"s{scenes}",
            setting="Kapanış",
            background=BACKGROUNDS[-1],
            characters=[first, second],
            lines=[
                Line(f"s{scenes}", first, "Bugün çok şey öğrendik.", seconds),
                Line(f"s{scenes}", second, "Yarın yine buluşalım!", seconds),
            ],
        )
    )
    return Episode(title=title, scenes=plan, language="tr")


def produce_episode(
    episode: Episode,
    out_dir: str | Path,
    *,
    language: str = "tr",
    use_voice: bool = True,
    voice_name: str | None = None,
) -> dict:
    """Bölümü üret ve bağımsız kapıdan geçir; tüm kanıtları diske yaz."""

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    (out / "brief.json").write_text(json.dumps({
        "title": episode.title,
        "language": language,
        "scenes": len(episode.scenes),
        "duration_seconds": round(episode.duration(), 2),
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    (out / "story.json").write_text(json.dumps({
        "title": episode.title,
        "language": language,
        "scenes": [
            {
                "scene_id": scene.scene_id,
                "setting": scene.setting,
                "background": scene.background,
                "characters": scene.characters,
                "lines": [
                    {"speaker": line.speaker, "text": line.text, "seconds": line.seconds}
                    for line in scene.lines
                ],
            }
            for scene in episode.scenes
        ],
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    voice = None
    if use_voice:
        voices = list_voices()
        voice = next((v for v in voices if voice_name and v.name == voice_name), None)
        if voice is None:
            voice = pick_voice(language, voices)

    track = None
    if voice is not None:
        timeline = episode_timeline(episode)
        clips = []
        for index, row in enumerate(timeline):
            wav = out / "voice" / f"line_{index:02d}.wav"
            synthesize_wav(row["text"], wav, voice=voice)
            clips.append((wav, row["start"], wav_duration(wav)))
        track = build_track(clips, episode.duration(), out / "voice" / "episode.wav")

    manifest = render_episode(episode, out, voice=voice.name if voice else None, audio=track)

    distinct_backgrounds = len({scene.background for scene in episode.scenes})
    report = verify_episode(
        manifest["video"],
        expected_scenes=manifest["scenes"],
        expected_duration=manifest["duration_seconds"],
        subtitles=manifest["subtitles"],
        expects_audio=voice is not None,
        expected_cuts=max(0, distinct_backgrounds - 1),
    )
    report["voice"] = (
        {"name": voice.name, "culture": voice.culture,
         "language_match": voice.culture.lower().startswith(language.lower())}
        if voice else None
    )
    report["manifest"] = manifest
    (out / "acceptance.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="çizgi film bölümü üret")
    parser.add_argument("brief", nargs="*", help="bölüm konusu")
    parser.add_argument("--out", required=True)
    parser.add_argument("--scenes", type=int, default=3)
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--no-voice", action="store_true")
    args = parser.parse_args(argv)

    brief = " ".join(args.brief).strip() or "Parkta bir gün"
    episode = storyboard(brief, scenes=args.scenes, seconds=args.seconds)
    report = produce_episode(episode, args.out, use_voice=not args.no_voice)
    summary = {
        "out": str(Path(args.out).resolve()),
        "passed": report["passed"],
        "score": report["score"],
        "duration_seconds": report["measurements"].get("duration_seconds"),
        "problems": report["problems"],
        "notes": report["notes"],
        "voice": report.get("voice"),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
