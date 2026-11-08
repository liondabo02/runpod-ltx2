import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
WWW = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\www")

targets = ["createMipilunaVoicePlayer", "MipilunaTeacherPack", "narrationStart", "voices/"]
for target in targets:
    hits = []
    for path in WWW.rglob("*.js"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if target in text:
            hits.append(path.name)
    for path in [WWW / "index.html"]:
        if path.exists() and target in path.read_text(encoding="utf-8", errors="replace"):
            hits.append("index.html")
    print(f"{target:26} -> {', '.join(sorted(set(hits))[:6]) or 'YOK'}")

print("\nvoicess klasoru:")
voices = WWW / "voices"
if voices.exists():
    for p in sorted(voices.glob("*")):
        print(f"  {p.name} · {round(p.stat().st_size/1024)} KB")
