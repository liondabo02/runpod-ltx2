from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def run(args: list[str], env: dict[str, str] | None = None) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, env=env or os.environ.copy(), check=True)


def enabled_language_codes() -> list[str]:
    cfg = yaml.safe_load((ROOT / "config" / "languages.yaml").read_text(encoding="utf-8"))
    return [x["code"] for x in cfg["languages"] if x.get("enabled", False)]


def main() -> None:
    ap = argparse.ArgumentParser(description="One-command recurring-character multilingual cartoon factory")
    ap.add_argument("idea", help="A word, prompt, or full episode idea")
    ap.add_argument("--episode-id", default="episode_001")
    ap.add_argument("--languages", default="all", help="all or comma-separated: tr,de,ar,fr,es")
    ap.add_argument("--skip-tts", action="store_true")
    args = ap.parse_args()

    episode_dir = ROOT / "output" / args.episode_id
    episode_dir.mkdir(parents=True, exist_ok=True)

    # 1) Master story + scene plan.
    run([PY, "orchestrator/main.py", args.idea, "--episode-id", args.episode_id])

    # 2) Shared music/SFX plan/audio. Reused by every language.
    env = os.environ.copy()
    env["JOBS_JSON"] = str(episode_dir / "jobs.json")
    run([PY, "workers/music_sfx.py"], env)

    # 3) Localize dialogue while preserving scene timing.
    run([PY, "workers/localize_episode.py", args.episode_id, "--languages", args.languages])

    codes = enabled_language_codes()
    if args.languages != "all":
        wanted = {x.strip() for x in args.languages.split(",") if x.strip()}
        codes = [x for x in codes if x in wanted]

    outputs: dict[str, str] = {}
    for lang in codes:
        # 4) Build per-language TTS/lipsync jobs.
        run([PY, "workers/build_language_jobs.py", args.episode_id, lang])

        # 5) Generate language-specific voice and mouth cues.
        if not args.skip_tts:
            run([PY, "workers/run_jobs.py", args.episode_id, "--language", lang])

        # 6) Render visual scenes into language-specific folders.
        lang_env = os.environ.copy()
        lang_env["EPISODE_JSON"] = str(episode_dir / f"episode_{lang}.json")
        lang_env["LANGUAGE"] = lang
        run([PY, "workers/sprite_renderer.py"], lang_env)

        # 7) Mix shared music + localized voices and concatenate episode.
        lang_env["EPISODE_ID"] = args.episode_id
        run([PY, "workers/finalize_episode.py"], lang_env)
        outputs[lang] = str(episode_dir / f"{args.episode_id}_{lang}.mp4")

    bundle = {
        "ok": True,
        "episode_id": args.episode_id,
        "idea": args.idea,
        "outputs": outputs,
    }
    (episode_dir / "delivery_manifest.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(bundle, ensure_ascii=False))


if __name__ == "__main__":
    main()
