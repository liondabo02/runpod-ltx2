"""Dizi komut satırı: sezon planla, bölüm üret, durumu yazdır.

    python -m ahos.series_cli --root <dizi-dizini> plan --episodes 50
    python -m ahos.series_cli --root <dizi-dizini> produce --episode 1
    python -m ahos.series_cli --root <dizi-dizini> status
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .series import (
    Character,
    SeriesBible,
    build_episode,
    load_state,
    plan_season,
    save_state,
    series_manifest,
)
from .studio_pipeline import produce_episode


def _bible(root: Path) -> SeriesBible:
    path = root / "series.json"
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        data["characters"] = [Character(**item) for item in data.get("characters", [])]
        return SeriesBible(**data)
    return SeriesBible(
        series_id=root.name or "dizi",
        title="Aden ve Kaan",
        premise="İki kardeş her bölüm yeni bir şey keşfeder.",
        characters=[
            Character("aden", "Aden", "female"),
            Character("kaan", "Kaan", "male"),
        ],
    )


def _save_bible(root: Path, series: SeriesBible) -> Path:
    path = root / "series.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(series_manifest(series), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

    parser = argparse.ArgumentParser(prog="ahos-series", description="dizi üretim hattı")
    parser.add_argument("--root", required=True, help="dizi dizini")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--scenes", type=int, default=4)
    parser.add_argument("--lines-per-scene", type=int, default=2)
    parser.add_argument("--line-seconds", type=float, default=3.0)
    parser.add_argument("--no-voice", action="store_true")
    parser.add_argument("command", choices=["plan", "produce", "status"])
    parser.add_argument("--episode", type=int, default=None)
    args = parser.parse_args(argv)

    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    series = _bible(root)
    _save_bible(root, series)
    state = load_state(root)

    if args.command == "plan":
        plans = plan_season(series, episodes=args.episodes)
        (root / "season.json").write_text(
            json.dumps([plan.__dict__ for plan in plans], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(json.dumps({"planned": len(plans), "first": plans[0].__dict__,
                          "file": str(root / "season.json")}, indent=2, ensure_ascii=False))
        return 0

    if args.command == "status":
        print(json.dumps({"series": series.title, "state": state}, indent=2, ensure_ascii=False))
        return 0

    number = args.episode or int(state.get("next_episode") or 1)
    plans = plan_season(series, episodes=max(number, int(state.get("planned") or args.episodes)))
    plan = plans[number - 1]
    episode = build_episode(series, plan, lines_per_scene=args.lines_per_scene,
                            line_seconds=args.line_seconds)
    out = root / "episodes" / f"b{number:02d}"
    report = produce_episode(episode, out, language=series.language, use_voice=not args.no_voice)

    state["produced"] = sorted(set(state.get("produced", [])) | {number})
    state["next_episode"] = number + 1
    state["planned"] = len(plans)
    state["last"] = {"number": number, "passed": report["passed"], "score": report["score"]}
    save_state(root, state)

    print(json.dumps({
        "episode": number,
        "title": plan.title,
        "out": str(out),
        "passed": report["passed"],
        "score": report["score"],
        "duration": report["measurements"].get("duration_seconds"),
        "voice": (report.get("voice") or {}).get("voice"),
        "problems": report["problems"],
    }, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
