from __future__ import annotations

import difflib
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .departments import utc_now

IGNORED_PARTS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "build",
    "dist",
    ".gradle",
}

_TEXT_SUFFIXES = {
    ".html",
    ".htm",
    ".js",
    ".css",
    ".json",
    ".md",
    ".txt",
    ".xml",
    ".py",
    ".yml",
    ".yaml",
}
_ASSET_RE = re.compile(
    r"""(?:src|href)\s*=\s*["']([^"'#?]+)["']"""
    r"""|url\(\s*["']?([^"')]+)["']?\s*\)""",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ChangedFile:
    path: str
    change: str
    diff: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "change": self.change, "diff": self.diff}


@dataclass(frozen=True, slots=True)
class AssetReport:
    root: Path
    web_root: Path
    referenced: int
    missing: tuple[str, ...]
    checked_files: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.missing


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_dir() or any(part in IGNORED_PARTS for part in path.parts):
            continue
        files.append(path)
    return files


def snapshot(root: str | Path) -> dict[str, str]:
    root_path = Path(root)
    result: dict[str, str] = {}
    for path in _iter_files(root_path):
        if path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        try:
            payload = path.read_bytes()
        except OSError:
            continue
        result[path.relative_to(root_path).as_posix()] = hashlib.sha256(
            payload
        ).hexdigest()
    return result


def _unified_diff(root: Path, relative: str, before: str | None) -> str:
    path = root / relative
    try:
        new_text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        new_text = []
    old_text = [] if before is None else before.splitlines()

    diff = difflib.unified_diff(
        old_text,
        new_text,
        fromfile=f"a/{relative}" if before is not None else "/dev/null",
        tofile=f"b/{relative}",
        lineterm="",
    )
    return "\n".join(diff)


def diff_snapshots(
    root: str | Path,
    before: dict[str, str],
    after: dict[str, str],
    *,
    before_texts: dict[str, str] | None = None,
) -> tuple[ChangedFile, ...]:
    root_path = Path(root)
    changed: list[ChangedFile] = []

    for relative, digest in after.items():
        if before.get(relative) == digest:
            continue
        texts = before_texts or {}
        changed.append(
            ChangedFile(
                path=relative,
                change="modified" if relative in before else "added",
                diff=_unified_diff(root_path, relative, texts.get(relative)),
            )
        )

    for relative in before:
        if relative in after:
            continue
        changed.append(
            ChangedFile(
                path=relative,
                change="removed",
                diff=_unified_diff(root_path, relative, None),
            )
        )

    changed.sort(key=lambda item: item.path)
    return tuple(changed)


def read_texts(root: str | Path, relative_paths: tuple[str, ...]) -> dict[str, str]:
    root_path = Path(root)
    texts: dict[str, str] = {}
    for relative in relative_paths:
        try:
            texts[relative] = (root_path / relative).read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            continue
    return texts


def detect_web_root(root: str | Path) -> Path:
    root_path = Path(root)
    for candidate in ("www", "public", "dist", "build", "."):
        if (root_path / candidate / "index.html").exists():
            return (root_path / candidate).resolve()
    return root_path.resolve()


def scan_assets(root: str | Path) -> AssetReport:
    """Find asset references in HTML/CSS that do not resolve on disk."""

    root_path = Path(root)
    web_root = detect_web_root(root_path)
    missing: list[str] = []
    checked: list[str] = []
    referenced = 0

    for path in web_root.rglob("*"):
        if path.is_dir() or path.suffix.lower() not in {".html", ".htm", ".css"}:
            continue
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        checked.append(path.relative_to(web_root).as_posix())
        for match in _ASSET_RE.finditer(text):
            target = (match.group(1) or match.group(2) or "").strip()
            if not target or target.startswith(
                ("http://", "https://", "data:", "mailto:", "//", "javascript:")
            ):
                continue
            referenced += 1
            candidate = (path.parent / target.split("?")[0].split("#")[0]).resolve()
            if not candidate.exists():
                missing.append(f"{path.relative_to(web_root).as_posix()} → {target}")

    return AssetReport(
        root=root_path,
        web_root=web_root,
        referenced=referenced,
        missing=tuple(sorted(set(missing))),
        checked_files=tuple(sorted(checked)),
    )


@dataclass(frozen=True, slots=True)
class PrecacheReport:
    declared: tuple[str, ...]
    missing_on_disk: tuple[str, ...]
    not_cached: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.missing_on_disk and not self.not_cached


_CORE_RE = re.compile(r"CORE_ASSETS\s*=\s*\[(.*?)\]\s*;", re.DOTALL)
_CACHEABLE_SUFFIXES = {".js", ".css", ".html"}
_CACHE_SKIP = {"sw.js", "precache.js"}


def _cacheable_assets(web_root: Path) -> list[str]:
    assets: list[str] = []
    for path in web_root.rglob("*"):
        if path.is_dir() or path.suffix.lower() not in _CACHEABLE_SUFFIXES:
            continue
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        relative = path.relative_to(web_root).as_posix()
        if relative in _CACHE_SKIP:
            continue
        assets.append(relative)
    return sorted(assets)


def scan_precache(root: str | Path) -> PrecacheReport:
    """Compare the service-worker precache list with the files on disk."""

    web_root = detect_web_root(root)
    precache = web_root / "precache.js"
    if not precache.exists():
        return PrecacheReport((), (), ())

    text = precache.read_text(encoding="utf-8", errors="replace")
    match = _CORE_RE.search(text)
    declared = (
        tuple(re.findall(r'"([^"]+)"', match.group(1))) if match else ()
    )

    missing = tuple(
        item for item in declared if not (web_root / item).exists()
    )
    declared_set = set(declared)
    not_cached = tuple(
        item for item in _cacheable_assets(web_root) if item not in declared_set
    )
    return PrecacheReport(declared, missing, not_cached)


def fix_precache(root: str | Path) -> tuple[str, ...]:
    """Add existing-but-uncached assets to CORE_ASSETS (real offline fix)."""

    web_root = detect_web_root(root)
    precache = web_root / "precache.js"
    report = scan_precache(root)
    if not precache.exists() or not report.not_cached:
        return ()

    text = precache.read_text(encoding="utf-8", errors="replace")
    match = _CORE_RE.search(text)
    if not match:
        return ()

    merged = sorted(set(report.declared) | set(report.not_cached))
    replacement = "CORE_ASSETS=[" + ",".join(f'"{item}"' for item in merged) + "];"
    precache.write_text(
        text[: match.start()] + replacement + text[match.end() :],
        encoding="utf-8",
    )
    return (
        f"{len(report.not_cached)} varlık çevrimdışı önbelleğe eklendi",
    )


def render_precache_report(report: PrecacheReport) -> str:
    lines = [
        "# Çevrimdışı Önbellek Denetimi",
        "",
        f"- **Bildirilen varlık:** {len(report.declared)}",
        f"- **Diskte eksik:** {len(report.missing_on_disk)}",
        f"- **Önbelleğe alınmamış:** {len(report.not_cached)}",
        "",
        "## Diskte bulunmayan kayıtlar",
        "",
    ]
    lines += [f"- `{item}`" for item in report.missing_on_disk] or ["Yok."]
    lines += ["", "## Önbelleğe alınmamış dosyalar", ""]
    lines += [f"- `{item}`" for item in report.not_cached] or ["Yok."]
    lines.append("")
    return "\n".join(lines)


def apply_web_hygiene(root: str | Path) -> tuple[str, ...]:
    """Deterministic, low-risk fixes for the game's entry HTML."""

    root_path = Path(root)
    web_root = detect_web_root(root_path)
    index = web_root / "index.html"
    if not index.exists():
        return ("index.html bulunamadı; düzeltme yapılmadı",)

    text = index.read_text(encoding="utf-8", errors="replace")
    applied: list[str] = []
    updated = text

    if re.search(r"<html(?![^>]*\blang=)", updated, re.IGNORECASE):
        updated = re.sub(
            r"<html(?![^>]*\blang=)" ,
            '<html lang="tr"',
            updated,
            count=1,
            flags=re.IGNORECASE,
        )
        applied.append('html etiketine lang="tr" eklendi')

    if not re.search(r'<meta[^>]+charset', updated, re.IGNORECASE):
        updated = re.sub(
            r"<head([^>]*)>",
            r'<head\1>\n  <meta charset="utf-8">',
            updated,
            count=1,
            flags=re.IGNORECASE,
        )
        applied.append("charset meta etiketi eklendi")

    if not re.search(r'name=["\']viewport["\']', updated, re.IGNORECASE):
        updated = re.sub(
            r"<head([^>]*)>",
            r'<head\1>\n  <meta name="viewport" content="width=device-width, initial-scale=1">',
            updated,
            count=1,
            flags=re.IGNORECASE,
        )
        applied.append("viewport meta etiketi eklendi")

    images_without_alt = len(
        re.findall(r"<img\b(?![^>]*\balt=)", updated, re.IGNORECASE)
    )
    if images_without_alt:
        updated = re.sub(
            r"<img\b(?![^>]*\balt=)",
            '<img alt=""',
            updated,
            flags=re.IGNORECASE,
        )
        applied.append(f"{images_without_alt} img etiketine alt eklendi (erişilebilirlik)")

    if updated != text:
        index.write_text(updated, encoding="utf-8")

    return tuple(applied)


_QUALITY_GATE = '''#!/usr/bin/env python3
"""Offline quality gate for this web game (ahos-gate-v2).

Checks that every asset referenced from HTML/CSS exists and that every
JavaScript/HTML/CSS file is listed in the service-worker precache.

Exit code 0 = clean, 1 = problems found.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover - non-reconfigurable stream
    pass

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "www" if (ROOT / "www" / "index.html").exists() else ROOT
REF = re.compile(r"""(?:src|href)\\s*=\\s*["']([^"'#?]+)["']""", re.I)


def main() -> int:
    problems: list[str] = []

    for path in WEB.rglob("*"):
        if path.suffix.lower() not in {".html", ".css"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in REF.finditer(text):
            target = match.group(1).strip()
            if target.startswith(("http://", "https://", "data:", "mailto:", "//", "#")):
                continue
            if not (path.parent / target.split("?")[0]).exists():
                problems.append(f"eksik varlık: {path.relative_to(WEB)} -> {target}")

    precache = WEB / "precache.js"
    if precache.exists():
        text = precache.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"CORE_ASSETS\\s*=\\s*\\[(.*?)\\]", text, re.S)
        declared = set(re.findall(r'"([^"]+)"', match.group(1))) if match else set()
        for path in WEB.rglob("*"):
            if path.suffix.lower() not in {".js", ".css", ".html"}:
                continue
            relative = path.relative_to(WEB).as_posix()
            if relative in {"sw.js", "precache.js"}:
                continue
            if relative not in declared:
                problems.append(f"önbellek dışı: {relative}")
        for item in sorted(declared):
            if not (WEB / item).exists():
                problems.append(f"disk üzerinde yok: {item}")

    if problems:
        print("\\n".join(problems))
        print(f"\\n{len(problems)} sorun bulundu.")
        return 1

    print("Çevrimdışı kalite kapısı: temiz.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def install_quality_gate(root: str | Path) -> tuple[str, ...]:
    """Install or upgrade the offline quality gate script (versioned)."""

    _guard(root)
    root_path = Path(root)
    tools = root_path / "tools"
    gate = tools / "check_offline.py"

    if gate.exists():
        # Projenin kendi kabul testi kullanıcıya aittir; üzerine yazmayız.
        # (Eski sürümlerde kodlama düzeltmesi QA alt sürecinde UTF-8 ortamıyla
        # yapılıyor, bu yüzden kapıyı değiştirmek gerekmiyor.)
        return ()

    tools.mkdir(parents=True, exist_ok=True)
    gate.write_text(_QUALITY_GATE, encoding="utf-8")
    return ("tools/check_offline.py kalite kapısı eklendi",)


def apply_focus_styles(root: str | Path) -> tuple[str, ...]:
    """Add keyboard focus rings for interactive game controls (idempotent)."""

    web_root = detect_web_root(root)
    css = web_root / "mobile.css"
    if not css.exists():
        return ()

    text = css.read_text(encoding="utf-8", errors="replace")
    additions: list[str] = []
    for selector in (".simulationBox", ".discoveryBadge"):
        rule = f"{selector}:focus-visible"
        if rule in text:
            continue
        text += f"{rule}{{outline:4px solid #34314d;outline-offset:4px}}"
        additions.append(f"{selector} odak halkası eklendi")

    if additions:
        css.write_text(text, encoding="utf-8")
    return tuple(additions)


CARD_KEYS_JS = """'use strict';
(function () {
  function enhance() {
    document.querySelectorAll('.card, [data-game]').forEach(function (el) {
      if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '0');
      if (!el.hasAttribute('role')) el.setAttribute('role', 'button');
    });
  }
  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    var el = event.target;
    if (!el || !el.matches || !el.matches('.card, [data-game]')) return;
    event.preventDefault();
    if (typeof el.click === 'function') el.click();
  }, true);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhance);
  } else {
    enhance();
  }
})();
"""


ARROW_NAV_JS = """
/* Arrow-key navigation between game cards (AHOS) */
(function () {
  var SELECTOR = '.card, [data-game]';
  document.addEventListener('keydown', function (event) {
    var keys = ['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp'];
    if (keys.indexOf(event.key) === -1) return;
    var items = Array.prototype.slice.call(document.querySelectorAll(SELECTOR));
    if (items.length < 2) return;
    var current = document.activeElement;
    var index = items.indexOf(current);
    if (index === -1) return;
    event.preventDefault();
    var step = (event.key === 'ArrowRight' || event.key === 'ArrowDown') ? 1 : -1;
    var next = items[(index + step + items.length) % items.length];
    if (next && typeof next.focus === 'function') next.focus();
  }, true);
  document.documentElement.setAttribute('data-ahos-nav', '1');
})();
"""


DUP_GUARD_JS = """
/* Tekrarli dokunma korumasi v2: yalniz ana menu kartlarinda (.card).
   Oyun ici hedefler (simulationBox, svg, canvas, #stage) etkilenmez. */
(function () {
  var WINDOW_MS = 350;
  var last = { key: null, at: 0 };
  function inGame(el) {
    return !!(el.closest && el.closest('#stage, .simulation, .miniSimulation, canvas, svg'));
  }
  function keyOf(el) {
    return el.id || el.getAttribute('data-game') || el.className || 'x';
  }
  document.addEventListener('click', function (event) {
    var el = event.target && event.target.closest ? event.target.closest('.card') : null;
    if (!el || inGame(el)) return;
    var now = Date.now();
    var key = keyOf(el);
    if (key === last.key && now - last.at < WINDOW_MS) {
      event.preventDefault();
      event.stopImmediatePropagation();
      return;
    }
    last = { key: key, at: now };
  }, true);
  document.documentElement.setAttribute('data-ahos-guard', '2');
})();
"""


PRESS_FEEDBACK_JS = """
/* Dokunma geri bildirimi: karta basinca kisa gorsel tepki (2-5 yas) */
(function () {
  var HOLD_MS = 180;
  document.addEventListener('pointerdown', function (event) {
    var el = event.target && event.target.closest ? event.target.closest('.card') : null;
    if (!el) return;
    el.classList.add('is-pressed');
    setTimeout(function () { el.classList.remove('is-pressed'); }, HOLD_MS);
  }, true);
  document.documentElement.setAttribute('data-ahos-press', '1');
})();
"""

PRESS_FEEDBACK_CSS = (
    ".card.is-pressed{transform:scale(.97);filter:brightness(.96)}"
    "@media(prefers-reduced-motion:reduce){.card.is-pressed{transform:none}}"
)


HINT_JS = """'use strict';
/* Uzun basinca ipucu: 2-5 yas icin sozel yonlendirme (AHOS) */
(function () {
  var HOLD_MS = 600;
  var timer = null;
  function region() {
    var node = document.getElementById('ahos-hint');
    if (node) return node;
    node = document.createElement('div');
    node.id = 'ahos-hint';
    node.setAttribute('role', 'status');
    node.setAttribute('aria-live', 'polite');
    node.style.cssText = 'position:fixed;left:12px;right:12px;bottom:16px;padding:12px;' +
      'border-radius:16px;background:#fdf6e3;color:#333;font-size:18px;z-index:9999;' +
      'box-shadow:0 4px 16px rgba(0,0,0,.18);display:none';
    document.body.appendChild(node);
    return node;
  }
  document.addEventListener('pointerdown', function (event) {
    var el = event.target && event.target.closest ? event.target.closest('.card') : null;
    if (!el) return;
    var label = el.getAttribute('aria-label') || el.textContent || 'Bu oyun';
    timer = setTimeout(function () {
      var node = region();
      node.textContent = label.trim().slice(0, 60) + ' — parmağını basılı tut, sonra bırak.';
      node.style.display = 'block';
      setTimeout(function () { node.style.display = 'none'; }, 2200);
    }, HOLD_MS);
  }, true);
  ['pointerup', 'pointercancel', 'pointerleave'].forEach(function (name) {
    document.addEventListener(name, function () {
      if (timer) { clearTimeout(timer); timer = null; }
    }, true);
  });
  document.documentElement.setAttribute('data-ahos-hint', '1');
})();
"""


def apply_hint_module(root: str | Path) -> tuple[str, ...]:
    """Add a long-press hint module (new file + script tag + precache entry)."""

    _guard(root)
    web_root = detect_web_root(root)
    index = web_root / "index.html"
    if not index.exists():
        return ()

    applied: list[str] = []
    module = web_root / "oyun-ipucu.js"
    if not module.exists():
        module.write_text(HINT_JS, encoding="utf-8")
        applied.append("oyun-ipucu.js eklendi")

    html = index.read_text(encoding="utf-8", errors="replace")
    if "oyun-ipucu.js" not in html:
        if "</body>" in html:
            html = html.replace(
                "</body>", '<script src="oyun-ipucu.js"></script></body>', 1
            )
        else:
            html += '<script src="oyun-ipucu.js"></script>'
        index.write_text(html, encoding="utf-8")
        applied.append("index.html'e oyun-ipucu.js bağlandı")

    precache = web_root / "precache.js"
    if precache.exists():
        text = precache.read_text(encoding="utf-8", errors="replace")
        if '"oyun-ipucu.js"' not in text:
            text = text.replace("[", '["oyun-ipucu.js",', 1)
            precache.write_text(text, encoding="utf-8")
            applied.append("önbelleğe oyun-ipucu.js eklendi")

    return tuple(applied)


ERROR_BOUNDARY_JS = """'use strict';
/* Hata siniri: beklenmedik bir hata oyunu kilitlemesin (AHOS) */
(function () {
  if (window.__ahosErrorBoundary) return;
  window.__ahosErrorBoundary = true;
  function show(detail) {
    if (document.getElementById('ahos-hata-kutu')) return;
    var style = document.createElement('style');
    style.textContent = '#ahos-hata-kutu{position:fixed;inset:0;background:rgba(31,35,64,.8);display:grid;place-items:center;z-index:99999;padding:20px}#ahos-hata-kutu .ahos-hata-kart{background:#fffdf6;border-radius:22px;padding:24px;max-width:420px;text-align:center}#ahos-hata-kutu h2{margin:0 0 8px;font-size:24px}#ahos-hata-kutu p{margin:0 0 16px;font-size:17px}#ahos-hata-kutu button{font-size:18px;padding:12px 20px;border-radius:16px;border:0;background:#8f7bd8;color:#fff}';
    document.head.appendChild(style);
    var box = document.createElement('div');
    box.id = 'ahos-hata-kutu';
    box.setAttribute('role', 'alert');
    box.innerHTML = '<div class="ahos-hata-kart"><h2>Bir aksaklik oldu</h2><p>Oyunu yeniden baslatmayi deneyelim.</p><button type="button">Tekrar dene</button></div>';
    box.querySelector('button').addEventListener('click', function () { location.reload(); });
    document.body.appendChild(box);
    try { console.warn('AHOS hata siniri:', detail); } catch (e) {}
  }
  window.addEventListener('error', function (event) {
    show(event && event.message ? event.message : 'error');
  });
  window.addEventListener('unhandledrejection', function (event) {
    show(event && event.reason ? String(event.reason) : 'rejection');
  });
})();
"""


PWA_MANIFEST = """{
  "id": "./",
  "name": "%NAME%",
  "short_name": "%NAME%",
  "start_url": "./index.html",
  "scope": "./",
  "display": "standalone",
  "background_color": "#fff8ed",
  "theme_color": "#fff8ed",
  "orientation": "any",
  "icons": []
}
"""

PWA_SW = """importScripts('./precache.js');
const CACHE = 'ahos-pwa-v1';
self.addEventListener('install', event => event.waitUntil((async () => {
  const cache = await caches.open(CACHE);
  await cache.addAll(CORE_ASSETS);
  await self.skipWaiting();
})()));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(event.request, { ignoreSearch: true });
    if (cached) return cached;
    try { return await fetch(event.request); }
    catch (error) {
      if (event.request.mode === 'navigate') return cache.match('index.html');
      throw error;
    }
  })());
});
"""


def apply_pwa_shell(root: str | Path) -> tuple[str, ...]:
    """Make the web app installable and offline-capable (idempotent)."""

    _guard(root)
    web_root = detect_web_root(root)
    index = web_root / "index.html"
    if not index.exists():
        return ()

    applied: list[str] = []
    manifest = web_root / "manifest.webmanifest"
    if not manifest.exists():
        name = root_path = Path(root).name or "AHOS"
        manifest.write_text(PWA_MANIFEST.replace("%NAME%", name), encoding="utf-8")
        applied.append("manifest.webmanifest eklendi")

    worker = web_root / "sw.js"
    if not worker.exists() and (web_root / "precache.js").exists():
        worker.write_text(PWA_SW, encoding="utf-8")
        applied.append("sw.js eklendi")

    html = index.read_text(encoding="utf-8", errors="replace")
    changed = html
    if "manifest.webmanifest" not in changed and 'rel="manifest"' not in changed:
        link = '<link rel="manifest" href="manifest.webmanifest">'
        if "</head>" in changed:
            changed = changed.replace("</head>", link + "</head>", 1)
        else:
            changed = "<head>" + link + "</head>" + changed
        applied.append("index.html'e manifest bağlandı")
    if "serviceWorker" not in changed and worker.exists():
        script = (
            "<script>if('serviceWorker' in navigator){window.addEventListener('load',"
            "function(){navigator.serviceWorker.register('sw.js').catch(function(){});});}</script>"
        )
        if "</body>" in changed:
            changed = changed.replace("</body>", script + "</body>", 1)
        else:
            changed = changed + script
        applied.append("index.html'e service worker kaydı eklendi")
    if changed != html:
        index.write_text(changed, encoding="utf-8")

    return tuple(applied)


def apply_error_boundary(root: str | Path) -> tuple[str, ...]:
    """Show a friendly retry card on unexpected JS errors instead of a dead screen."""

    _guard(root)
    web_root = detect_web_root(root)
    index = web_root / "index.html"
    if not index.exists():
        return ()

    applied: list[str] = []
    module = web_root / "hata-siniri.js"
    if not module.exists():
        module.write_text(ERROR_BOUNDARY_JS, encoding="utf-8")
        applied.append("hata-siniri.js eklendi")

    html = index.read_text(encoding="utf-8", errors="replace")
    if "hata-siniri.js" not in html:
        if "</body>" in html:
            html = html.replace(
                "</body>", '<script src="hata-siniri.js"></script></body>', 1
            )
        else:
            html += '<script src="hata-siniri.js"></script>'
        index.write_text(html, encoding="utf-8")
        applied.append("index.html'e hata-siniri.js bağlandı")

    precache = web_root / "precache.js"
    if precache.exists():
        text = precache.read_text(encoding="utf-8", errors="replace")
        if '"hata-siniri.js"' not in text:
            text = text.replace("[", '["hata-siniri.js",', 1)
            precache.write_text(text, encoding="utf-8")
            applied.append("önbelleğe hata-siniri.js eklendi")

    return tuple(applied)


TEXT_SCALE_JS = """'use strict';
/* Buyuk yazi modu: 2-5 yas icin okunabilirlik (AHOS) */
(function () {
  var KEY = 'ahos-buyuk-yazi';
  function apply(on) {
    document.body.classList.toggle('ahos-buyuk-yazi', !!on);
  }
  function build() {
    if (document.getElementById('ahos-yazi-dugme')) return;
    var button = document.createElement('button');
    button.id = 'ahos-yazi-dugme';
    button.type = 'button';
    button.textContent = 'A+';
    button.setAttribute('aria-label', 'Yazıyı büyüt veya küçült');
    button.setAttribute('aria-pressed', 'false');
    button.style.cssText = 'position:fixed;right:12px;top:12px;z-index:9998;' +
      'min-width:56px;min-height:56px;border-radius:50%;border:0;font-size:20px;' +
      'background:#34314d;color:#fff;box-shadow:0 4px 12px rgba(0,0,0,.25)';
    button.addEventListener('click', function () {
      var on = !document.body.classList.contains('ahos-buyuk-yazi');
      apply(on);
      button.setAttribute('aria-pressed', on ? 'true' : 'false');
      try { localStorage.setItem(KEY, on ? '1' : '0'); } catch (e) {}
    });
    document.body.appendChild(button);
  }
  var stored = '0';
  try { stored = localStorage.getItem(KEY) || '0'; } catch (e) {}
  apply(stored === '1');
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', build);
  } else {
    build();
  }
  document.documentElement.setAttribute('data-ahos-yazi', '1');
})();
"""

TEXT_SCALE_CSS = (
    "body.ahos-buyuk-yazi{font-size:118%}"
    "body.ahos-buyuk-yazi .card{font-size:1.06em;padding:22px}"
    "body.ahos-buyuk-yazi button{min-height:56px;min-width:56px}"
)


def apply_text_scale(root: str | Path) -> tuple[str, ...]:
    """Add a persisted large-text mode for young children (3 files, idempotent)."""

    _guard(root)
    web_root = detect_web_root(root)
    index = web_root / "index.html"
    if not index.exists():
        return ()

    applied: list[str] = []
    module = web_root / "oyun-yazi.js"
    if not module.exists():
        module.write_text(TEXT_SCALE_JS, encoding="utf-8")
        applied.append("oyun-yazi.js eklendi")

    html = index.read_text(encoding="utf-8", errors="replace")
    if "oyun-yazi.js" not in html:
        if "</body>" in html:
            html = html.replace(
                "</body>", '<script src="oyun-yazi.js"></script></body>', 1
            )
        else:
            html += '<script src="oyun-yazi.js"></script>'
        index.write_text(html, encoding="utf-8")
        applied.append("index.html'e oyun-yazi.js bağlandı")

    css = web_root / "mobile.css"
    if css.exists():
        text = css.read_text(encoding="utf-8", errors="replace")
        if "ahos-buyuk-yazi" not in text:
            css.write_text(text + TEXT_SCALE_CSS, encoding="utf-8")
            applied.append("büyük yazı CSS kuralları eklendi")

    precache = web_root / "precache.js"
    if precache.exists():
        text = precache.read_text(encoding="utf-8", errors="replace")
        if '"oyun-yazi.js"' not in text:
            text = text.replace("[", '["oyun-yazi.js",', 1)
            precache.write_text(text, encoding="utf-8")
            applied.append("önbelleğe oyun-yazi.js eklendi")

    return tuple(applied)


def _guard(root: str | Path | None = None) -> None:
    """Stop a cancelled mission (or a stale thread) before it writes to disk."""

    from . import mission_guard, project_locks
    from .mission_guard import MissionCancelled

    mission_guard.guard()
    if root is None:
        return
    if not project_locks.probe(root):
        return
    # Kilit tutuluyor: yalnız bu sürecin kendi görevi ve doğru token ile yazabilir.
    # Alt thread'lere contextvars taşınmadığı için token yoksa yazma reddedilir.
    token = mission_guard.current()
    owner = project_locks.owned_by(root)
    if token is None or owner != token.mission_id:
        raise MissionCancelled(
            "proje kilidi: proje başka bir görev/süreç tarafından tutuluyor "
            f"(owner={owner or 'dış süreç'}); yazma reddedildi"
        )


def apply_press_feedback(root: str | Path) -> tuple[str, ...]:
    """Add a short visual press response for game cards (idempotent)."""

    _guard(root)
    web_root = detect_web_root(root)
    applied: list[str] = []

    module = web_root / "card-keys.js"
    if module.exists():
        text = module.read_text(encoding="utf-8", errors="replace")
        if "data-ahos-press" not in text:
            module.write_text(text + PRESS_FEEDBACK_JS, encoding="utf-8")
            applied.append("dokunma geri bildirimi (JS) eklendi")

    css = web_root / "mobile.css"
    if css.exists():
        text = css.read_text(encoding="utf-8", errors="replace")
        if ".card.is-pressed" not in text:
            css.write_text(text + PRESS_FEEDBACK_CSS, encoding="utf-8")
            applied.append("dokunma geri bildirimi (CSS) eklendi")

    return tuple(applied)


def apply_card_keyboard(root: str | Path) -> tuple[str, ...]:
    """Keyboard activation (Enter/Space) for game cards; idempotent."""

    _guard(root)
    web_root = detect_web_root(root)
    index = web_root / "index.html"
    if not index.exists():
        return ()

    applied: list[str] = []
    module = web_root / "card-keys.js"
    if not module.exists():
        module.write_text(CARD_KEYS_JS, encoding="utf-8")
        applied.append("card-keys.js eklendi")

    html = index.read_text(encoding="utf-8", errors="replace")
    if 'card-keys.js' not in html:
        if "</body>" in html:
            html = html.replace(
                "</body>",
                '<script src="card-keys.js"></script></body>',
                1,
            )
        else:
            html += '<script src="card-keys.js"></script>'
        index.write_text(html, encoding="utf-8")
        applied.append("index.html'e card-keys.js betiği bağlandı")

    current = module.read_text(encoding="utf-8", errors="replace")
    if "data-ahos-guard', '2'" not in current:
        # Eski v1 (tum kartlar) korumasini v2 (yalniz ana menu kartlari) ile
        # degistir; modul bilinen bloklardan deterministik olarak yeniden yazilir.
        module.write_text(
            CARD_KEYS_JS + ARROW_NAV_JS + DUP_GUARD_JS, encoding="utf-8"
        )
        applied.append("tekrarlı dokunma koruması v2 (oyun içi hedefler muaf)")

    precache = web_root / "precache.js"
    if precache.exists():
        text = precache.read_text(encoding="utf-8", errors="replace")
        if '"card-keys.js"' not in text:
            text = text.replace(
                '"card-keys.js"', '"card-keys.js"'
            ).replace(
                "[",
                '["card-keys.js",',
                1,
            )
            precache.write_text(text, encoding="utf-8")
            applied.append("önbellek listesine card-keys.js eklendi")

    return tuple(applied)


def render_asset_report(report: AssetReport) -> str:
    lines = [
        "# Görsel Varlık Denetimi",
        "",
        f"- **Proje:** `{report.root}`",
        f"- **Web kökü:** `{report.web_root}`",
        f"- **Taranan dosya:** {len(report.checked_files)}",
        f"- **Referans:** {report.referenced}",
        f"- **Eksik:** {len(report.missing)}",
        "",
        "## Eksik varlıklar",
        "",
    ]
    lines += [f"- {item}" for item in report.missing] or ["Eksik varlık yok."]
    lines += ["", "## Taranan dosyalar", ""]
    lines += [f"- `{item}`" for item in report.checked_files] or ["- yok"]
    lines.append("")
    return "\n".join(lines)


def render_changes(changes: tuple[ChangedFile, ...], applied: tuple[str, ...]) -> str:
    lines = ["# Kod Değişikliği Kanıtı", ""]
    lines.append(f"- **Zaman:** {utc_now()}")
    lines.append(f"- **Değişen dosya:** {len(changes)}")
    lines.append("")
    lines.append("## Uygulanan düzeltmeler")
    lines.append("")
    lines += [f"- {item}" for item in applied] or ["- değişiklik yok"]
    lines += ["", "## Değişen dosyalar", ""]
    if changes:
        lines.append("| Dosya | Tür |")
        lines.append("| --- | --- |")
        lines += [f"| `{item.path}` | {item.change} |" for item in changes]
    else:
        lines.append("Değişiklik yok.")
    lines.append("")
    return "\n".join(lines)


def make_project_executor(
    project_root: str | Path,
    artifacts_root: str | Path,
):
    """Worker executor that really edits a bound project and records proof."""

    from .worker_runtime import WorkerExecutionResult
    from .workforce_execution import WorkItem

    root = Path(project_root)
    out_root = Path(artifacts_root)

    def _execute(item: WorkItem, worker_id: str):
        try:
            return _run_step(item, worker_id)
        except Exception as exc:  # noqa: BLE001 - surface the real reason
            return WorkerExecutionResult(
                task_id=item.task_id,
                worker_id=worker_id,
                success=False,
                summary=(
                    f"proje adımı {item.task_id.rsplit(':', 1)[-1]} hata verdi: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

    def _run_step(item: WorkItem, worker_id: str):
        step = item.task_id.rsplit(":", 1)[-1]
        safe_task = re.sub(r"[^A-Za-z0-9._-]+", "_", item.task_id).strip("._") or "task"
        destination = out_root / safe_task
        destination.mkdir(parents=True, exist_ok=True)

        before = snapshot(root)
        before_texts = read_texts(root, tuple(before))

        if step == "brief":
            report = scan_assets(root)
            precache = scan_precache(root)
            path = destination / "ASSET_REPORT.md"
            path.write_text(
                render_asset_report(report)
                + "\n\n"
                + render_precache_report(precache),
                encoding="utf-8",
            )
            summary = (
                f"varlık denetimi: {report.referenced} referans, "
                f"{len(report.missing)} eksik; önbellek dışı {len(precache.not_cached)}"
            )
        elif step == "produce":
            applied = list(apply_web_hygiene(root))
            applied.extend(apply_card_keyboard(root))
            applied.extend(apply_focus_styles(root))
            applied.extend(apply_press_feedback(root))
            applied.extend(apply_hint_module(root))
            applied.extend(apply_text_scale(root))
            applied.extend(apply_error_boundary(root))
            applied.extend(apply_pwa_shell(root))
            applied.extend(fix_precache(root))
            applied.extend(install_quality_gate(root))
            after = snapshot(root)
            changes = diff_snapshots(root, before, after, before_texts=before_texts)
            diff_path = destination / "CHANGES.diff"
            diff_path.write_text(
                "\n\n".join(item.diff for item in changes) or "(değişiklik yok)",
                encoding="utf-8",
            )
            path = destination / "CHANGES.md"
            path.write_text(render_changes(changes, tuple(applied)), encoding="utf-8")
            summary = (
                f"{len(changes)} dosya değişti; {len(applied)} düzeltme uygulandı"
            )
        else:
            report = scan_assets(root)
            path = destination / "VERIFY.md"
            path.write_text(
                "# Doğrulama\n\n"
                f"- Eksik varlık: {len(report.missing)}\n"
                f"- Referans: {report.referenced}\n",
                encoding="utf-8",
            )
            summary = f"doğrulama: {len(report.missing)} eksik varlık"

        acceptance_report = scan_assets(root)
        accepted = step == "brief" or not acceptance_report.missing
        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=accepted,
            summary=summary if accepted else f"Doğrulama başarısız: {len(acceptance_report.missing)} eksik varlık; {summary}",
            artifacts=(str(path),),
        )

    return _execute
