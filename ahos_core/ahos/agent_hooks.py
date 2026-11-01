"""Claude Code'dan tersine mühendislik: deterministik kancalar (hooks).

Claude Code'un "hooks" fikri: model ne yaparsa yapsın, **beltirli anlarda
deterministik kontroller** çalışır ve gerekirse işlemi bloklar. Bizde karşılığı:

- `pre_edit`  : düzenleme öncesi yol/güvenlik kontrolleri (kopya dizin, gizli
                dosya, izin verilmeyen uzantı).
- `post_edit` : düzenleme sonrası sözdizimi kontrolü (.py derle, .js node --check,
                .json parse, .html temel denge kontrolü).

Kanca çıktısı `HookResult(allowed, detail)`; bloklanırsa çağıran geri alır.
"""

from __future__ import annotations

import json
import os
import py_compile
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

FORBIDDEN_PARTS = {"android", "ios", "node_modules", ".git", "build", "dist", ".gradle"}
ALLOWED_SUFFIXES = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".css", ".html", ".htm",
    ".json", ".md", ".txt", ".svg", ".yml", ".yaml", ".toml",
}
MAX_BYTES = 2_000_000


@dataclass(frozen=True)
class HookResult:
    allowed: bool
    detail: str = ""


def pre_edit(path: str, *, root: Path, content: bytes | None = None, require_exists: bool = True) -> HookResult:
    """Düzenleme öncesi: yol ve boyut kontrolü."""

    parts = set(Path(path).parts)
    forbidden = parts & FORBIDDEN_PARTS
    if forbidden:
        return HookResult(False, f"kopya/hedef dışı dizin: {', '.join(sorted(forbidden))}")
    if Path(path).name.startswith("."):
        return HookResult(False, "gizli dosya düzenlenemez")
    if Path(path).suffix.lower() not in ALLOWED_SUFFIXES:
        return HookResult(False, f"izin verilmeyen uzantı: {Path(path).suffix}")
    if content is not None and len(content) > MAX_BYTES:
        return HookResult(False, f"içerik çok büyük: {len(content)} bayt")
    if require_exists and not (Path(root) / path).exists():
        return HookResult(False, f"hedef dosya yok: {path}")
    return HookResult(True, "")


def post_edit(path: str, *, root: Path) -> HookResult:
    """Düzenleme sonrası: dile göre sözdizimi kontrolü."""

    target = Path(root) / path
    if not target.exists():
        return HookResult(False, f"dosya kayboldu: {path}")
    suffix = target.suffix.lower()
    try:
        if suffix == ".py":
            compiled = tempfile.NamedTemporaryFile(suffix=".pyc", delete=False)
            compiled.close()
            try:
                py_compile.compile(str(target), cfile=compiled.name, doraise=True)
            finally:
                Path(compiled.name).unlink(missing_ok=True)
            return HookResult(True, "python sözdizimi tamam")
        if suffix in {".json"}:
            json.loads(target.read_text(encoding="utf-8", errors="replace"))
            return HookResult(True, "json geçerli")
        if suffix in {".js", ".mjs", ".cjs"}:
            if os.environ.get("AHOS_NODE_CHECK", "1").strip().lower() in {"0", "false", "no"}:
                return HookResult(True, "node kontrolü kapalı")
            done = subprocess.run(
                ["node", "--check", str(target)],
                capture_output=True, text=True, timeout=30,
            )
            if done.returncode != 0:
                return HookResult(False, "js sözdizimi: " + (done.stderr or "")[:300].strip())
            return HookResult(True, "js sözdizimi tamam")
        if suffix in {".html", ".htm"}:
            text = target.read_text(encoding="utf-8", errors="replace")
            if text.count("<script") != text.count("</script"):
                return HookResult(False, "html: script etiketi dengesiz")
            return HookResult(True, "html temel kontrol tamam")
    except subprocess.TimeoutExpired:
        return HookResult(False, f"sözdizimi kontrolü zaman aşımı: {path}")
    except (py_compile.PyCompileError, json.JSONDecodeError, OSError) as exc:
        return HookResult(False, f"{suffix} hatası: {exc}")
    return HookResult(True, "kontrol yok (uzantı)")
