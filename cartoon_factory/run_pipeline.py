from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def run(args: list[str], env: dict[str, str] | None = None) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, env=env or os.environ.copy(), check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="One-command recurring-character cartoon factory")
    ap.add_argument("idea", help="Natural-language episode idea")
    ap.add_argument("--episode-id", default="episode_001")
    ap.add_argument("--skip-tts", action="store_true")
    args = ap.parse_args()

    episode_dir = ROOT / "output" / args.episode_id
    run([PY, "orchestrator/main.py", args.idea, "--episode-id", args.episode_id])

    env = os.environ.copy()
    env["JOBS_JSON"] = str(episode_dir / "jobs.json")
    run([PY, "workers/music_sfx.py"], env)

    if not args.skip_tts:
        run([PY, "workers/run_jobs.py", args.episode_id])

    env["EPISODE_JSON"] = str(episode_dir / "episode.json")
    run([PY, "workers/sprite_renderer.py"], env)

    env["EPISODE_ID"] = args.episode_id
    run([PY, "workers/finalize_episode.py"], env)

    print(f"DONE: {episode_dir / (args.episode_id + '.mp4')}")


if __name__ == "__main__":
    main()
