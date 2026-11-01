"""Oyun üretimi: brief'ten oynanabilir HTML5 oyunu + bağımsız denetim.

Repo'da oyun departmanı vardı ama "oyun yap" dendiğinde çalıştırılabilir bir
çıktı üretmiyordu. Bu modül tek dosyalık, tarayıcıda açılan bir oyun üretir:

- Canvas 2D, klavye/dokunmatik kontrol, skor, çarpışma, yeniden başlatma
- Tema parametreleri (renk, karakter adı, toplanacak nesne)
- Deterministik şablon: aynı brief → aynı oyun (test edilebilir)

Denetim (`audit_game`) beş şeyi ölçer; biri bile eksikse teslim sayılmaz:
1. dosya var ve ≥ 3 KB
2. `<canvas>` ve `getContext('2d')` var
3. oyun döngüsü (`requestAnimationFrame`) var
4. klavye dinleyicisi var
5. JavaScript sözdizimi `node --check` ile geçerli (node varsa)
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

TEMPLATE = """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{title} — tarayıcıda oynanan, klavye ve dokunmatik destekli küçük bir oyun.">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{title} — tarayıcıda oynanan küçük bir oyun.">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🎮</text></svg>">
<link rel="manifest" href="site.webmanifest">
<title>{title}</title>
<style>
  html, body {{ margin: 0; height: 100%; background: {bg}; color: #fff;
    font-family: system-ui, sans-serif; overflow: hidden; }}
  #wrap {{ display: flex; flex-direction: column; align-items: center; justify-content: center;
    height: 100%; gap: 8px; }}
  canvas {{ background: {sky}; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,.5);
    touch-action: none; }}
  #hud {{ font-size: 18px; letter-spacing: .5px; }}
  #hint {{ opacity: .7; font-size: 14px; }}
</style>
</head>
<body>
<div id="wrap">
  <div id="hud">Skor: <span id="score">0</span> · Can: <span id="lives">3</span></div>
  <h1 style="margin:0;font-size:20px">{title}</h1>
  <canvas id="game" width="800" height="480" role="application" aria-label="{title} oyun alanı"></canvas>
  <div id="hint">{hint}</div>
</div>
<script>
(function () {{
  const canvas = document.getElementById('game');
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const scoreEl = document.getElementById('score');
  const livesEl = document.getElementById('lives');

  const state = {{ score: 0, lives: 3, over: false, t: 0 }};
  const player = {{ x: W / 2, y: H - 60, w: 54, h: 40, speed: 6 }};
  const keys = {{ left: false, right: false }};
  let items = [];
  let clouds = [];

  function reset() {{
    state.score = 0; state.lives = 3; state.over = false; state.t = 0;
    player.x = W / 2; items = []; clouds = [];
    for (let i = 0; i < 6; i++) {{
      clouds.push({{ x: Math.random() * W, y: 40 + Math.random() * 120, s: 1 + Math.random() }});
    }}
    spawn(); spawn(); spawn();
    scoreEl.textContent = '0'; livesEl.textContent = '3';
  }}

  function spawn() {{
    items.push({{ x: 40 + Math.random() * (W - 80), y: -20,
                 r: 12 + Math.random() * 8, vy: 1.6 + Math.random() * 1.8 }});
  }}

  function update(dt) {{
    if (state.over) return;
    state.t += dt;
    if (keys.left) player.x -= player.speed;
    if (keys.right) player.x += player.speed;
    player.x = Math.max(player.w / 2, Math.min(W - player.w / 2, player.x));

    clouds.forEach(c => {{ c.x -= 0.2 * c.s; if (c.x < -80) c.x = W + 80; }});

    for (const item of items) {{
      item.y += item.vy;
      const dx = Math.abs(item.x - player.x);
      const dy = Math.abs(item.y - player.y);
      if (dx < player.w / 2 + item.r && dy < player.h / 2 + item.r) {{
        item.dead = true; state.score += 10; scoreEl.textContent = state.score;
      }}
      if (item.y > H + 30) {{
        item.dead = true; state.lives -= 1; livesEl.textContent = state.lives;
        if (state.lives <= 0) state.over = true;
      }}
    }}
    items = items.filter(i => !i.dead);
    if (items.length < 3 && Math.random() < 0.04) spawn();
  }}

  function draw() {{
    ctx.fillStyle = '{sky}';
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = 'rgba(255,255,255,.75)';
    clouds.forEach(c => {{
      ctx.beginPath();
      ctx.arc(c.x, c.y, 22 * c.s, 0, Math.PI * 2);
      ctx.arc(c.x + 26 * c.s, c.y + 6, 16 * c.s, 0, Math.PI * 2);
      ctx.arc(c.x - 26 * c.s, c.y + 8, 14 * c.s, 0, Math.PI * 2);
      ctx.fill();
    }});
    ctx.fillStyle = '{ground}';
    ctx.fillRect(0, H - 28, W, 28);

    ctx.fillStyle = '{item_color}';
    items.forEach(i => {{
      ctx.beginPath(); ctx.arc(i.x, i.y, i.r, 0, Math.PI * 2); ctx.fill();
    }});

    ctx.fillStyle = '{player_color}';
    ctx.beginPath();
    ctx.roundRect(player.x - player.w / 2, player.y - player.h / 2, player.w, player.h, 10);
    ctx.fill();

    if (state.over) {{
      ctx.fillStyle = 'rgba(0,0,0,.65)'; ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.font = 'bold 44px system-ui';
      ctx.fillText('Oyun bitti', W / 2, H / 2 - 10);
      ctx.font = '24px system-ui';
      ctx.fillText('Skor: ' + state.score + ' · Yeniden başlatmak için boşluk', W / 2, H / 2 + 36);
      ctx.textAlign = 'left';
    }}
  }}

  let last = performance.now();
  function loop(now) {{
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    update(dt);
    draw();
    requestAnimationFrame(loop);
  }}

  window.addEventListener('keydown', e => {{
    if (e.key === 'ArrowLeft' || e.key === 'a') keys.left = true;
    if (e.key === 'ArrowRight' || e.key === 'd') keys.right = true;
    if (e.key === ' ' && state.over) reset();
  }});
  window.addEventListener('keyup', e => {{
    if (e.key === 'ArrowLeft' || e.key === 'a') keys.left = false;
    if (e.key === 'ArrowRight' || e.key === 'd') keys.right = false;
  }});
  canvas.addEventListener('pointerdown', e => {{
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    if (x < W / 2) keys.left = true; else keys.right = true;
  }});
  canvas.addEventListener('pointerup', () => {{ keys.left = false; keys.right = false; }});

  reset();
  requestAnimationFrame(loop);
}})();
</script>
</body>
</html>
"""


@dataclass
class GameBrief:
    title: str = "Meyve Topla"
    hero: str = "kahraman"
    item_name: str = "meyve"
    sky: str = "#9ad0f5"
    ground: str = "#4c9a3f"
    player_color: str = "#2f6fd0"
    item_color: str = "#e2483c"
    bg: str = "#0d1117"


def build_game(brief: GameBrief, out_dir: str | Path) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    hint = (f"← → veya A/D ile {brief.hero} hareket eder; "
            f"düşen {brief.item_name}leri topla. Dokunmatikte sağa/sola bas.")
    html = TEMPLATE.format(
        title=brief.title, sky=brief.sky, ground=brief.ground,
        player_color=brief.player_color, item_color=brief.item_color,
        bg=brief.bg, hint=hint,
    )
    index = out / "index.html"
    index.write_text(html, encoding="utf-8")
    (out / "site.webmanifest").write_text(json.dumps({
        "name": brief.title,
        "short_name": brief.title[:12],
        "start_url": "./index.html",
        "display": "fullscreen",
        "background_color": brief.bg,
        "theme_color": brief.sky,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "title": brief.title,
        "hero": brief.hero,
        "item": brief.item_name,
        "file": str(index),
        "bytes": index.stat().st_size,
    }
    (out / "game.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def audit_game(index: str | Path) -> dict:
    path = Path(index)
    problems: list[str] = []
    measurements: dict = {}

    if not path.is_file():
        return {"passed": False, "problems": ["index.html yok"], "measurements": {}}

    text = path.read_text(encoding="utf-8", errors="replace")
    size = path.stat().st_size
    measurements["bytes"] = size
    if size < 3000:
        problems.append(f"dosya çok küçük: {size} bayt")

    checks = {
        "canvas": "<canvas" in text,
        "context": "getContext('2d')" in text or 'getContext("2d")' in text,
        "loop": "requestAnimationFrame" in text,
        "keyboard": "addEventListener('keydown'" in text or 'addEventListener("keydown"' in text,
        "score": "score" in text.lower(),
        "restart": "reset()" in text,
    }
    measurements.update(checks)
    for name, ok in checks.items():
        if not ok:
            problems.append(f"eksik: {name}")

    script_match = re.search(r"<script>(.*?)</script>", text, re.S)
    if script_match:
        script = script_match.group(1)
        node = shutil.which("node")
        if node:
            import tempfile

            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
                handle.write(script)
                temp_path = handle.name
            try:
                result = subprocess.run([node, "--check", temp_path], capture_output=True, text=True, timeout=60)
                measurements["syntax_ok"] = result.returncode == 0
                if result.returncode != 0:
                    problems.append("JavaScript sözdizimi hatası: " + (result.stderr or "")[-160:])
            finally:
                Path(temp_path).unlink(missing_ok=True)
        else:
            measurements["syntax_ok"] = None

    return {
        "passed": not problems,
        "problems": problems,
        "measurements": measurements,
        "scope": "yapı + sözdizimi; oynanış dengesi ve görsel kalite doğrulanmaz",
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="HTML5 oyun üret")
    parser.add_argument("brief", nargs="*", help="oyun konusu")
    parser.add_argument("--out", required=True)
    parser.add_argument("--title", default=None)
    args = parser.parse_args(argv)

    text = " ".join(args.brief).strip() or "meyve toplama"
    brief = GameBrief(title=args.title or text.title()[:40], hero="kahraman", item_name=text)
    manifest = build_game(brief, args.out)
    report = audit_game(manifest["file"])
    print(json.dumps({"manifest": manifest, "gate": report}, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
