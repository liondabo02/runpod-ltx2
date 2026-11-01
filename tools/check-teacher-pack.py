import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
WWW = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\www")

pack = WWW / "teacher-voice-pack.js"
text = pack.read_text(encoding="utf-8", errors="replace")
print("teacher-voice-pack.js:", len(text), "karakter")

refs = sorted(set(re.findall(r"voices/[A-Za-z0-9_./-]+", text)))
print("referans sayisi:", len(refs))
missing = []
for ref in refs:
    path = WWW / ref
    if not path.exists():
        missing.append(ref)
print("eksik dosya:", len(missing))
for ref in missing[:20]:
    print("  EKSIK:", ref)
for ref in refs[:10]:
    print("  var:", ref)

if len(refs) == 0:
    print("--- dosyadan ilk 60 satir ---")
    for line in text.splitlines()[:60]:
        print(line[:140])
