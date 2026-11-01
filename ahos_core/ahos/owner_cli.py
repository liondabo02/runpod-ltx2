from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .owner_console import build_default_console

CARTOON = re.compile(r"(?i)\b(çizgi\s*film|çizgi\s*dizi|animasyon|bölüm|episode|cartoon)\b")


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    return cleaned[:48] or "bolum"


def _default_runtime_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "runtime"


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover - non-reconfigurable stream
        pass

    parser = argparse.ArgumentParser(
        prog="ahos-owner",
        description="Tek satırlık sahip komutu: departman kur, iş ver, durum sor.",
    )
    parser.add_argument(
        "command",
        nargs="*",
        help="ör. 'çizgi film departmanı kur' veya 'landing page yap'",
    )
    parser.add_argument(
        "--runtime-dir",
        default=str(_default_runtime_dir()),
        help="departman defteri ve artefaktların tutulacağı dizin",
    )
    parser.add_argument("--scenes", type=int, default=3, help="çizgi film sahne sayısı")
    parser.add_argument("--seconds", type=float, default=3.0, help="replik süresi (sn)")
    parser.add_argument("--no-voice", action="store_true", help="seslendirme yapma")
    args = parser.parse_args(argv)

    runtime_dir = Path(args.runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    text = " ".join(args.command).strip() or "durum"

    # Çizgi film talebi doğrudan stüdyo hattına gider: belge değil bölüm üretir.
    if CARTOON.search(text) and "departman" not in text.casefold():
        from .studio_pipeline import produce_episode, storyboard

        brief = re.sub(r"(?i)\b(çizgi\s*film|çizgi\s*dizi|animasyon|bölüm|episode|cartoon|yap|üret)\b", " ", text)
        brief = " ".join(brief.split()) or text
        out = runtime_dir / "studio-episodes" / _slug(brief)
        episode = storyboard(brief, scenes=max(1, args.scenes), seconds=args.seconds)
        report = produce_episode(episode, out, use_voice=not args.no_voice)
        print(f"Bölüm: {out}")
        print(f"Video: {out / 'episode.mp4'}")
        print(f"Kapı : {'GEÇTİ' if report['passed'] else 'KALDI'} (skor {report['score']})")
        for problem in report["problems"]:
            print(f"  - {problem}")
        for note in report["notes"]:
            print(f"  · {note}")
        voice = report.get("voice")
        if voice:
            print(f"Ses  : {voice['name']} ({voice['culture']})")
        return 0 if report["passed"] else 1

    console = build_default_console(runtime_dir)
    result = console.handle(text)

    print(result.message)
    if result.mission is not None:
        print(f"\nGörev durumu: {result.mission.status.value}")
        for step in result.mission.steps:
            print(f"  - {step.step.step_id}: {step.stage.value} ({step.reason})")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
