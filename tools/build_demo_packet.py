"""Claude'a yüklenecek demo paketini oluştur (kod + kanıt + video)."""
from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "AHOS-Studio-Demo.zip"
FILES = [
    "PROJECT-DEMO.md", "DEMO-PROMPT.txt",
    "docs/CAPABILITY-MATRIX.md", "docs/INSTALL-LOG.md", "docs/STUDIO-SKILLS.md",
    "ahos_core/ahos/studio_2d.py", "ahos_core/ahos/studio_voice.py",
    "ahos_core/ahos/studio_pipeline.py", "ahos_core/ahos/series.py",
    "ahos_core/ahos/lipsync.py", "ahos_core/ahos/studio_qa.py",
    "ahos_core/ahos/studio_skills.py", "ahos_core/ahos/visual_pipeline.py",
    "ahos_core/tests/test_studio_2d.py", "ahos_core/tests/test_studio_voice.py",
    "ahos_core/tests/test_lipsync.py", "ahos_core/tests/test_series.py",
    "ahos_core/tests/test_studio_pipeline.py",
    "tools/render_aden_voiced_clip.py", "tools/qa_voiced_clip.py",
    "tools/studio_backends/rig_factory.py", "tools/studio_backends/verify_rig.py",
    "studio/jobs/aden-clip/aden_idle_5s_voiced.mp4",
    "studio/jobs/aden-clip/aden_idle_5s.mp4",
    "studio/jobs/aden-clip/preview_voiced.png", "studio/jobs/aden-clip/preview.png",
    "studio/jobs/aden-clip/qa_voiced.json", "studio/jobs/aden-clip/qa.json",
    "studio/jobs/aden-clip/README.md",
    "studio/jobs/aden-rig/lipsync/aden-line.wav",
    "studio/jobs/aden-rig/lipsync/aden-line.json",
    "studio/jobs/aden-rig/lipsync/lipsync-contract.json",
]


def main() -> int:
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            path = ROOT / name
            if not path.is_file():
                print("MISSING", name)
                continue
            archive.write(path, arcname=name)
        log = subprocess.run(["git", "log", "--oneline", "-12"], cwd=ROOT,
                             capture_output=True, text=True)
        archive.writestr("GIT-LOG.txt", log.stdout)
    print("ZIP", OUT, OUT.stat().st_size, "bytes", len(FILES), "entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
