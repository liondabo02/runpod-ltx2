"""Cinecode (Claude skill) bağımsız QC adaptörü — orijinal kodu değiştirmez."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
DEFAULT = Path(os.environ.get("CINECODE_HOME", r"C:\Users\esmak\.claude\skills\cinecode"))


def status(home: Path = DEFAULT) -> dict:
    scripts = home / "scripts"
    return {
        "home": str(home),
        "exists": home.is_dir(),
        "scripts": {name: (scripts / name).is_file()
                    for name in ("make.py", "qc.py", "capture.mjs", "tts.py", "mix.py")},
        "node": shutil.which("node"),
        "python": sys.executable,
        "ffmpeg": shutil.which("ffmpeg"),
        "claude_cli": shutil.which("claude"),
    }


def qc(video: Path, out: Path, home: Path = DEFAULT) -> dict:
    script = home / "scripts" / "qc.py"
    if not script.is_file():
        raise SystemExit(f"cinecode qc.py bulunamadı: {script}")
    checks = {}
    for name in ("info", "black", "freeze", "dup"):
        result = subprocess.run([sys.executable, str(script), name, str(video)],
                                capture_output=True, text=True)
        checks[name] = {"exit": result.returncode, "stdout": result.stdout.strip(),
                        "stderr": result.stderr.strip()[:400]}
    payload = {"schema": "ahos.studio.cinecode-qc.v1", "video": str(video),
               "sha256": __import__("hashlib").sha256(video.read_bytes()).hexdigest(),
               "status": status(home), "checks": checks}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video")
    parser.add_argument("--out", default=str(ROOT / "studio" / "pipeline" / "cinecode" / "qc-report.json"))
    parser.add_argument("--home", default=str(DEFAULT))
    args = parser.parse_args(argv)
    home = Path(args.home)
    if not args.video:
        print(json.dumps(status(home), ensure_ascii=False, indent=2))
        return 0
    payload = qc(Path(args.video), Path(args.out), home)
    print(json.dumps({key: payload["checks"][key]["exit"] for key in payload["checks"]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
