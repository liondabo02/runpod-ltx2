"""Oyun cilası: yumuşak animasyonlar + çoklu çocuk profili.

1) Animasyonlar: kart/buton geçişleri, karakter nefes animasyonu, doğru cevap
   nabzı, konfeti zaten var.
2) Profil: `mipiluna.profile` anahtarı; oyun verisi profil başına saklanır
   (kardeşler ayrı ilerleme). Veli paneli profil değiştirebilir.
"""

from __future__ import annotations

import io
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
WWW = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\www")
GAME = WWW / "sokak-oyunlari.html"
PARENT = WWW / "veli.html"

CSS_EXTRA = """
  @keyframes floaty { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }
  @keyframes pop { 0%{transform:scale(1)} 40%{transform:scale(1.08)} 100%{transform:scale(1)} }
  @keyframes glow { 0%,100%{box-shadow:0 0 0 #0000} 50%{box-shadow:0 0 24px #5b86ff88} }
  .game{animation:floaty 6s ease-in-out infinite}
  .game:nth-child(2n){animation-delay:.6s}
  .game:active{transform:scale(.98)}
  button.primary{animation:glow 3.4s ease-in-out infinite}
  .toast.show{animation:pop .3s ease}
  .cell.done{animation:pop .28s ease}
"""


def patch_game() -> None:
    text = GAME.read_text(encoding="utf-8", errors="replace")
    changed = False

    if "floaty" not in text:
        text = text.replace("</style>", CSS_EXTRA + "</style>", 1)
        changed = True

    if "PROFILE_KEY" not in text:
        text = text.replace(
            "  var KEY = 'mipiluna.sokak.v2';",
            "  var PROFILE_KEY = 'mipiluna.profile';\n"
            "  var profile = 'cocuk1';\n"
            "  try { profile = localStorage.getItem(PROFILE_KEY) || 'cocuk1'; } catch(e){}\n"
            "  var KEY = 'mipiluna.sokak.v2.' + profile;",
        )
        changed = True
        # profil göstergesi
        text = text.replace(
            '<span class="pill" id="totalPill">⭐ 0</span>',
            '<span class="pill" id="profilePill">👦 ' + "profil" + '</span>\n'
            '    <span class="pill" id="totalPill">⭐ 0</span>',
        )
        text = text.replace(
            "document.getElementById('totalPill').textContent = '⭐ ' + (state.total || 0);",
            "document.getElementById('totalPill').textContent = '⭐ ' + (state.total || 0);\n"
            "  var pp = document.getElementById('profilePill');\n"
            "  if (pp) pp.textContent = '👦 ' + profile;",
        )

    if changed:
        GAME.write_text(text, encoding="utf-8")
        print("oyun: animasyon + profil eklendi")
    else:
        print("oyun: zaten güncel")


def patch_parent() -> None:
    text = PARENT.read_text(encoding="utf-8", errors="replace")
    if "profileSelect" in text:
        print("veli: profil seçici zaten var")
        return
    text = text.replace(
        '<div style="margin-left:auto"><a class="pill" href="sokak-oyunlari.html">← Oyunlara dön</a></div>',
        '<div style="margin-left:auto;display:flex;gap:8px;align-items:center">'
        '<select id="profileSelect" class="pill" aria-label="Çocuk profili">'
        '<option value="cocuk1">Çocuk 1</option>'
        '<option value="cocuk2">Çocuk 2</option>'
        '<option value="cocuk3">Çocuk 3</option>'
        "</select>"
        '<a class="pill" href="sokak-oyunlari.html">← Oyunlara dön</a></div>',
    )
    text = text.replace(
        "  var STORE = 'mipiluna.sokak.v2';",
        "  var PROFILE_KEY = 'mipiluna.profile';\n"
        "  var profile = 'cocuk1';\n"
        "  try { profile = localStorage.getItem(PROFILE_KEY) || 'cocuk1'; } catch(e){}\n"
        "  var STORE = 'mipiluna.sokak.v2.' + profile;",
    )
    text = text.replace(
        "  var state = {};",
        "  var select = document.getElementById('profileSelect');\n"
        "  if (select){\n"
        "    select.value = profile;\n"
        "    select.addEventListener('change', function(){\n"
        "      try { localStorage.setItem(PROFILE_KEY, this.value); } catch(e){}\n"
        "      location.reload();\n"
        "    });\n"
        "  }\n"
        "  var state = {};",
    )
    PARENT.write_text(text, encoding="utf-8")
    print("veli: profil seçici eklendi")


patch_game()
patch_parent()

for page in (GAME, PARENT):
    text = page.read_text(encoding="utf-8", errors="replace")
    scripts = re.findall(r"<script>(.*?)</script>", text, flags=re.S)
    ok = True
    for script in scripts:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
            handle.write(script)
            path = handle.name
        done = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        if done.returncode != 0:
            ok = False
            print(page.name, "JS HATA:", done.stderr[:300])
    print(page.name, "JS:", "OK" if ok else "HATA")
