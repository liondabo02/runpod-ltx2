"""Claude Code'un `CLAUDE.md` karşılığı: proje hafızası (`AHOS.md`).

Her proje kökünde `AHOS.md` bulunur; içinde komutlar, düzen ve kurallar yazar.
Model istemine bu dosya eklenir; böylece her görevde "nasıl çalışılır" bilgisi
tek yerden gelir (kopyala-yapıştır istem yok).

Biçim:

    # Proje
    ## Komutlar
    - test: pytest -q
    - lint: node --check app.js
    ## Kurallar
    - `android/` altına yazma
    ## Düzen
    - kaynak: `www/`
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

MEMORY_FILE = "AHOS.md"


@dataclass
class ProjectMemory:
    commands: dict[str, str] = field(default_factory=dict)
    rules: tuple[str, ...] = ()
    layout: tuple[str, ...] = ()
    raw: str = ""

    def prompt_block(self, limit: int = 1200) -> str:
        if not self.raw:
            return ""
        lines = ["### Proje hafızası (AHOS.md)"]
        if self.commands:
            lines.append("Komutlar: " + ", ".join(f"{k}={v}" for k, v in self.commands.items()))
        if self.rules:
            lines += ["Kurallar:"] + [f"- {rule}" for rule in self.rules]
        if self.layout:
            lines += ["Düzen:"] + [f"- {item}" for item in self.layout]
        text = "\n".join(lines)
        return text[:limit]


def parse_memory(text: str) -> ProjectMemory:
    """`AHOS.md` metnini yapılandırılmış hafızaya çevirir."""

    commands: dict[str, str] = {}
    rules: list[str] = []
    layout: list[str] = []
    section = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        low = line.casefold()
        if line.startswith("##"):
            section = low.lstrip("# ").strip()
            continue
        if not line.startswith("- "):
            continue
        body = line[2:].strip()
        if section.startswith("komut") and ":" in body:
            key, value = body.split(":", 1)
            commands[key.strip()] = value.strip()
        elif section.startswith("kural"):
            rules.append(body)
        elif section.startswith("düzen") or section.startswith("duzen"):
            layout.append(body)
    return ProjectMemory(commands=commands, rules=tuple(rules), layout=tuple(layout), raw=text)


def load_memory(root: str | Path, limit: int = 6000) -> ProjectMemory:
    """Proje kökündeki `AHOS.md` dosyasını okur (yoksa boş)."""

    path = Path(root) / MEMORY_FILE
    if not path.exists():
        return ProjectMemory()
    text = path.read_text(encoding="utf-8", errors="replace")[:limit]
    return parse_memory(text)


def default_memory(root: str | Path) -> str:
    """Proje yapısına bakıp başlangıç `AHOS.md` içeriği üretir."""

    base = Path(root)
    commands: list[str] = []
    if (base / "package.json").exists():
        try:
            payload = json.loads((base / "package.json").read_text(encoding="utf-8"))
            scripts = payload.get("scripts") or {}
            if "test" in scripts:
                commands.append(f"- test: {scripts['test']}")
            if "build" in scripts:
                commands.append(f"- build: {scripts['build']}")
        except (json.JSONDecodeError, OSError):
            pass
    if (base / "tests").is_dir() or (base / "tools").is_dir():
        commands.append("- test: python -m pytest -q")
    if not commands:
        commands.append("- test: python -m pytest -q")

    layout: list[str] = []
    for name in ("www", "src", "app", "tests", "tools", "docs"):
        if (base / name).is_dir():
            layout.append(f"- kaynak: `{name}/`")

    lines = [
        "# Proje",
        "",
        "## Komutlar",
        *commands,
        "",
        "## Kurallar",
        "- kopya dizinlere (`android/`, `ios/`, `build/`) yazma; kaynağı düzenle",
        "- her değişiklikten sonra test komutunu çalıştır",
        "- olmayan dosya adı uydurma; envanterden seç",
        "",
        "## Düzen",
        *(layout or ["- kaynak: proje kökü"]),
        "",
    ]
    return "\n".join(lines)


def ensure_memory(root: str | Path) -> Path:
    """`AHOS.md` yoksa oluşturur; yolunu döndürür."""

    path = Path(root) / MEMORY_FILE
    if not path.exists():
        path.write_text(default_memory(root), encoding="utf-8")
    return path
