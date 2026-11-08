import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
f = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\www\index.html")
text = f.read_text(encoding="utf-8", errors="replace")

m = re.search(r"<title>([^<]*)</title>", text)
print("baslik:", m.group(1) if m else "-")
ids = sorted(set(re.findall(r'id="([A-Za-z0-9_-]{3,24})"', text)))
print("id sayisi:", len(ids))
print("ornek id:", ", ".join(ids[:25]))
attrs = sorted(set(re.findall(r"data-[a-z-]+", text)))
print("data nitelikleri:", ", ".join(attrs[:20]) or "-")

for line in text.splitlines():
    low = line.lower()
    if "menu" in low and len(line) < 300:
        print("MENU:", line.strip()[:160])
