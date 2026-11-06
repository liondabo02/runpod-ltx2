"""Rakip analizi sonrası: uyarlanabilir zorluk + oynama süresi takibi.

- state.adaptive[game]: 0.88–1.15 arası otomatik zorluk çarpanı
  * çocuk başarılıysa zorluk hafifçe artar (max 1.15)
  * üst üste başarısızsa düşer (min 0.88)  → "adaptive learning progression"
- state.minutes: günlük oynama süresi (veli paneli için)
- levelScale() artık adaptive çarpanını da içerir
"""

import io
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
f = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\www\sokak-oyunlari.html")
text = f.read_text(encoding="utf-8", errors="replace")

if "adaptive" in text:
    print("uyarlanabilir zorluk zaten var")
else:
    text = text.replace(
        "var state = { stars:{}, total:0, muted:false, slow:false, level:1, unlocked:{} };",
        "var state = { stars:{}, total:0, muted:false, slow:false, level:1, unlocked:{}, "
        "adaptive:{}, minutes:0, day:'' };",
    )

    # günlük süre sayacı
    text = text.replace(
        "  function save(){ try { localStorage.setItem(KEY, JSON.stringify(state)); } catch(e){} }",
        "  function save(){ try { localStorage.setItem(KEY, JSON.stringify(state)); } catch(e){} }\n"
        "  function trackTime(dt){\n"
        "    var today = new Date().toISOString().slice(0,10);\n"
        "    if (state.day !== today){ state.day = today; state.minutes = 0; }\n"
        "    state.minutes = (state.minutes || 0) + dt / 60;\n"
        "    if (Math.floor(state.minutes * 10) % 6 === 0) save();\n"
        "  }",
    )

    # levelScale: uyarlanabilir çarpan
    text = text.replace(
        "  function levelScale(){ return 0.85 + 0.15 * (window.__level - 1); }",
        "  function levelScale(){\n"
        "    var id = current && current.meta ? current.meta.id : '';\n"
        "    var adaptive = (state.adaptive && state.adaptive[id]) || 1;\n"
        "    return (0.85 + 0.15 * (window.__level - 1)) * adaptive;\n"
        "  }",
    )

    # finish: başarıda zorluk artır
    text = text.replace(
        "    state.unlocked[id] = Math.max(state.unlocked[id] || 1, Math.min(3, lv + 1));",
        "    state.unlocked[id] = Math.max(state.unlocked[id] || 1, Math.min(3, lv + 1));\n"
        "    state.adaptive = state.adaptive || {};\n"
        "    state.adaptive[id] = Math.min(1.15, (state.adaptive[id] || 1) + 0.04);",
    )

    # fail: zorluğu düşür
    text = text.replace(
        "  function fail(text){\n    running = false; play('k-03-yanlis');",
        "  function fail(text){\n    running = false; play('k-03-yanlis');\n"
        "    var fid = current && current.meta ? current.meta.id : '';\n"
        "    state.adaptive = state.adaptive || {};\n"
        "    state.adaptive[fid] = Math.max(0.88, (state.adaptive[fid] || 1) - 0.06);\n"
        "    save();",
    )

    # döngüde süre takibi
    text = text.replace(
        "    if (running){ clock += dt; current.update(dt, now / 1000); }",
        "    if (running){ clock += dt; trackTime(dt); current.update(dt, now / 1000); }",
    )

    # başlık çubuğuna veli paneli bağlantısı
    text = text.replace(
        '    <span class="pill" id="totalPill">⭐ 0</span>',
        '    <a class="pill" id="parentLink" href="veli.html" target="_blank" rel="noopener">👨‍👩‍👧 Veli</a>\n'
        '    <span class="pill" id="totalPill">⭐ 0</span>',
    )

    f.write_text(text, encoding="utf-8")
    print("uyarlanabilir zorluk + süre takibi eklendi")

scripts = re.findall(r"<script>(.*?)</script>", text, flags=re.S)
for script in scripts:
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        path = handle.name
    done = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    print("JS:", "OK" if done.returncode == 0 else "HATA")
    if done.returncode != 0:
        print(done.stderr[:400])
