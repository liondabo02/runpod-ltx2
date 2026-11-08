"""Sokak oyunlarına 3 seviyeli ilerleme sistemi ekler.

- Seviye 1/2/3 düğmeleri (kilitli seviye açılmaz)
- Yıldızlar seviye bazında saklanır: state.stars[game] = [s1,s2,s3]
- Seviye, oyun hızını ölçekler (0.85 / 1.0 / 1.2)
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

if "levelBar" in text:
    print("seviye sistemi zaten var")
else:
    # 1) HUD'a seviye düğmeleri
    text = text.replace(
        '      <div class="bar"><i id="energy"></i></div>\n    </div>',
        '      <div class="bar"><i id="energy"></i></div>\n'
        '      <span class="pill" id="levelBar">Seviye '
        '<button class="lv" data-lv="1">1</button>'
        '<button class="lv" data-lv="2">2</button>'
        '<button class="lv" data-lv="3">3</button></span>\n    </div>',
    )

    # 2) durum: seviye ve seviye bazlı yıldızlar
    text = text.replace(
        "var state = { stars:{}, total:0, muted:false, slow:false };",
        "var state = { stars:{}, total:0, muted:false, slow:false, level:1, unlocked:{} };",
    )

    # 3) finish(): seviye bazlı yıldız + sonraki seviyeyi aç
    text = text.replace(
        "    if ((state.stars[current.meta.id] || 0) < stars) state.stars[current.meta.id] = stars;",
        "    var id = current.meta.id, lv = state.level;\n"
        "    var arr = state.stars[id] || [0,0,0];\n"
        "    if ((arr[lv-1] || 0) < stars) arr[lv-1] = stars;\n"
        "    state.stars[id] = arr;\n"
        "    state.unlocked[id] = Math.max(state.unlocked[id] || 1, Math.min(3, lv + 1));",
    )

    # 4) seviye ölçeği: oyunlara global aktarım
    text = text.replace(
        "  function startGame(meta){",
        "  window.__level = 1;\n"
        "  function levelScale(){ return 0.85 + 0.15 * (window.__level - 1); }\n"
        "  function startGame(meta){",
    )

    # 5) menüde seviye yıldızlarını göster
    text = text.replace(
        "'<div class=\"stars\">' + starText(state.stars[game.id] || 0) + '</div>';",
        "'<div class=\"stars\">' + (state.stars[game.id] || [0,0,0]).map(function(v){ return starText(v); }).join(' ') + '</div>';",
    )

    # 6) seviye düğmelerini bağla
    anchor = "  renderMenu();"
    block = (
        "  function setLevel(lv){\n"
        "    state.level = lv; window.__level = lv; save();\n"
        "    var bar = document.getElementById('levelBar');\n"
        "    if (bar){ bar.querySelectorAll('.lv').forEach(function(b){\n"
        "      b.classList.toggle('on', Number(b.dataset.lv) === lv);\n"
        "    }); }\n"
        "    if (current && current.meta) startGame(current.meta);\n"
        "  }\n"
        "  document.querySelectorAll('.lv').forEach(function(btn){\n"
        "    btn.addEventListener('click', function(){\n"
        "      var lv = Number(this.dataset.lv);\n"
        "      var unlocked = (state.unlocked[current && current.meta ? current.meta.id : ''] || 1);\n"
        "      if (lv > unlocked){ toast('Önce ' + (lv-1) + '. seviyeyi bitir'); return; }\n"
        "      setLevel(lv);\n"
        "    });\n"
        "  });\n"
        "  window.__level = state.level || 1;\n"
        "  renderMenu();"
    )
    text = text.replace(anchor, block, 1)

    # 7) Saklambaç dışındaki oyunlarda da hız ölçeği kullan
    text = text.replace(
        "        var speed = 190 + survived * 6;",
        "        var speed = (190 + survived * 6) * levelScale();",
    )
    text = text.replace(
        "        spawn = Math.max(0.45, 1.2 - survived * 0.025);",
        "        spawn = Math.max(0.35, 1.2 - survived * 0.025) / levelScale();",
    )
    text = text.replace(
        "      var speed = onPlatform ? 40 : 118 + survived * 2.2;",
        "      var speed = (onPlatform ? 40 : (118 + survived * 2.2) * levelScale());",
    )
    text = text.replace(
        "      towers = []; ballsLeft = 10; ball = null; aim = null;",
        "      towers = []; ballsLeft = Math.max(6, 11 - window.__level * 2); ball = null; aim = null;",
    )

    f.write_text(text, encoding="utf-8")
    print("seviye sistemi eklendi")

# sözdizimi
scripts = re.findall(r"<script>(.*?)</script>", text, flags=re.S)
for script in scripts:
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        path = handle.name
    done = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    print("JS:", "OK" if done.returncode == 0 else "HATA")
    if done.returncode != 0:
        print(done.stderr[:400])
print("levelBar:", "levelBar" in text, "| setLevel:", "function setLevel" in text)
