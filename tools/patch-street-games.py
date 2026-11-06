import io
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
f = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\www\sokak-oyunlari.html")
text = f.read_text(encoding="utf-8", errors="replace")

# 1) meta referansları
text = text.replace(
    "if ((state.stars[current.id] || 0) < stars) state.stars[current.id] = stars;",
    "if ((state.stars[current.meta.id] || 0) < stars) state.stars[current.meta.id] = stars;",
)
text = text.replace(
    "current = new Seksek(); current.setup(); current.draw(ctx, 0);",
    "current = new Seksek(); current.meta = GAMES[0]; current.setup(); current.draw(ctx, 0);",
)
text = text.replace("if (current) play(current.hint);", "if (current && current.meta) play(current.meta.hint);")
text = text.replace("if (current) play(current.teacher);", "if (current && current.meta) play(current.meta.teacher);")

# 2) zorluk kontrolü
if "diffBtn" in text and "addEventListener" in text and "DIFFS" not in text:
    anchor = "  document.getElementById('totalPill').textContent"
    block = (
        "  var DIFFS = [{label:'🎚️ Kolay', v:0.85}, {label:'🎚️ Normal', v:1.0}, {label:'🎚️ Zor', v:1.25}];\n"
        "  var diffIndex = (typeof state.diff === 'number') ? state.diff : 1;\n"
        "  window.__diff = DIFFS[diffIndex].v;\n"
        "  document.getElementById('diffBtn').textContent = DIFFS[diffIndex].label;\n"
        "  document.getElementById('diffBtn').addEventListener('click', function(){\n"
        "    diffIndex = (diffIndex + 1) % DIFFS.length;\n"
        "    window.__diff = DIFFS[diffIndex].v;\n"
        "    this.textContent = DIFFS[diffIndex].label;\n"
        "    state.diff = diffIndex; save();\n"
        "    toast('Zorluk: ' + DIFFS[diffIndex].label.replace('🎚️ ',''));\n"
        "    if (current && current.meta) startGame(current.meta);\n"
        "  });\n"
        "  document.getElementById('totalPill').textContent"
    )
    text = text.replace(anchor, block, 1)

f.write_text(text, encoding="utf-8")

scripts = re.findall(r"<script>(.*?)</script>", text, flags=re.S)
print("diffBtn:", "diffBtn" in text, "| DIFFS:", "DIFFS" in text, "| script blok:", len(scripts))
for script in scripts:
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        path = handle.name
    done = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    print("JS:", "OK" if done.returncode == 0 else "HATA")
    if done.returncode != 0:
        print(done.stderr[:500])
