import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
f = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\www\index.html")
text = f.read_text(encoding="utf-8", errors="replace")

for match in re.finditer(r'data-game="([^"]+)"', text):
    start = max(0, match.start() - 220)
    print("---", match.group(1))
    print(text[start:match.start() + 60].replace("\n", " ")[-260:])

print("\nmain kapanisi:", text.find("</main>"), "| body:", text.find("<body"))
