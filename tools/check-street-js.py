import io
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
html = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\www\sokak-oyunlari.html").read_text(encoding="utf-8", errors="replace")

scripts = re.findall(r"<script>(.*?)</script>", html, flags=re.S)
print("script blok:", len(scripts), "| toplam uzunluk:", sum(len(s) for s in scripts))

for index, script in enumerate(scripts):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        path = handle.name
    completed = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    status = "OK" if completed.returncode == 0 else "HATA"
    print(f"  blok {index}: {status}")
    if completed.returncode != 0:
        print(completed.stderr[:400])
