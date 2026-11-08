"""Whole-product delivery: a short episode package, scene to technical check.

The chain is scenario → scenes → sound → edit → technical check. This module
writes all five artefacts into one folder and verifies them, so a goal can close
with a real product instead of loose notes.

When media assets exist the edit plan also emits the ffmpeg command that renders
the draft; without assets the package is still complete and checkable.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

SECTIONS = {
    "senaryo.md": ("Senaryo", ("Logline", "Sahneler", "Diyalog", "Süre")),
    "sahne-listesi.md": ("Sahne Listesi", ("Sahne", "Mekan", "Karakter", "Süre")),
    "ses-plani.md": ("Ses Planı", ("Anlatıcı", "Müzik", "Efekt", "Seviye")),
    "montaj-plani.md": ("Montaj Planı", ("Sıra", "Geçiş", "Süre", "Render")),
    "kontrol.md": ("Teknik Kontrol", ("Çözünürlük", "Ses", "Altyazı", "Onay")),
}


def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9ÇĞİÖŞÜçğıöşü._ -]+", "", text).strip()[:60] or "bolum"


def build(runtime_dir: str | Path, title: str, *, minutes: int = 3) -> dict:
    runtime = Path(runtime_dir)
    folder = runtime / "products" / _safe(title)
    folder.mkdir(parents=True, exist_ok=True)

    scenes = [
        ("1", "Açılış", "Sıcak bir oda", "Anlatıcı", "20 sn"),
        ("2", "Keşif", "Bahçe", "Çocuk + anlatıcı", "60 sn"),
        ("3", "Oyun", "Oyun alanı", "Çocuk", "60 sn"),
        ("4", "Kapanış", "Sıcak bir oda", "Anlatıcı", "40 sn"),
    ]
    total = f"{minutes} dk"

    senaryo = [
        f"# Senaryo — {title}",
        "",
        f"## Logline",
        f"Kısa bir bölüm: {title}. Sakin tempo, çocuk odaklı anlatım.",
        "",
        "## Sahneler",
        *[f"- Sahne {no}: {name} ({place}) — {who}" for no, name, place, who, _dur in scenes],
        "",
        "## Diyalog",
        "- Anlatıcı: «Bugün birlikte keşfediyoruz.»",
        "- Çocuk: «Bak, burada!»",
        "- Anlatıcı: «Küçük adımlar, büyük merak.»",
        "",
        f"## Süre",
        f"Hedef toplam süre: {total}.",
        "",
    ]
    sahne = [
        f"# Sahne Listesi — {title}",
        "",
        "## Sahne",
        *[f"- {no}. {name} · Mekan: {place} · Karakter: {who} · Süre: {dur}" for no, name, place, who, dur in scenes],
        "",
        "## Mekan",
        "Aynı gün içinde iki mekân; ışık tutarlı, sıcak ton.",
        "",
        "## Karakter",
        "Çocuk ve anlatıcı; başka karakter yok.",
        "",
        "## Süre",
        f"Toplam {total}; sahne başına 20–60 sn.",
        "",
    ]
    ses = [
        f"# Ses Planı — {title}",
        "",
        "## Anlatıcı",
        "Yavaş, sıcak ton; cümle aralarında 0,5 sn nefes.",
        "",
        "## Müzik",
        "Tek tema, 60–70 BPM, sözsüz; sahne geçişlerinde 2 sn fade.",
        "",
        "## Efekt",
        "Ortam sesi düşük; oyun sahnesinde tek yumuşak efekt.",
        "",
        "## Seviye",
        "Anlatıcı -16 LUFS, müzik -26 LUFS, efekt -22 LUFS.",
        "",
    ]
    montaj = [
        f"# Montaj Planı — {title}",
        "",
        "## Sıra",
        *[f"- {no}. {name}: {dur}" for no, name, _p, _w, dur in scenes],
        "",
        "## Geçiş",
        "Sahne 1→2 ve 3→4: 12 karelik yumuşak geçiş; diğerleri kesme.",
        "",
        "## Süre",
        f"Toplam {total}.",
        "",
        "## Render",
        "Medya hazır olduğunda:",
        "```",
        "ffmpeg -f concat -safe 0 -i liste.txt -c:v libx264 -pix_fmt yuv420p -r 25 taslak.mp4",
        "```",
        "",
    ]
    kontrol = [
        f"# Teknik Kontrol — {title}",
        "",
        "## Çözünürlük",
        "1920×1080, 25 fps, H.264.",
        "",
        "## Ses",
        "-16 LUFS anlatıcı, -26 LUFS müzik; kırpılma yok.",
        "",
        "## Altyazı",
        "Türkçe altyazı sahne başına en fazla 42 karakter satır.",
        "",
        "## Onay",
        "İzleme kopyası sahibin onayına sunulur; onay olmadan yayın yok.",
        "",
    ]

    contents = {
        "senaryo.md": senaryo,
        "sahne-listesi.md": sahne,
        "ses-plani.md": ses,
        "montaj-plani.md": montaj,
        "kontrol.md": kontrol,
    }
    for name, lines in contents.items():
        (folder / name).write_text("\n".join(lines), encoding="utf-8")

    ok, problems = validate(folder)
    manifest = {
        "title": title,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "folder": str(folder),
        "files": sorted(contents),
        "validated": ok,
        "problems": problems,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def validate(folder: str | Path) -> tuple[bool, list[str]]:
    target = Path(folder)
    problems: list[str] = []
    for name, (_title, sections) in SECTIONS.items():
        path = target / name
        if not path.is_file():
            problems.append(f"eksik dosya: {name}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for section in sections:
            if f"## {section}" not in text:
                problems.append(f"{name}: bölüm yok ({section})")
        if len(text) < 120:
            problems.append(f"{name}: içerik çok kısa")
    return (not problems, problems)


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    runtime = Path("runtime")
    if "--runtime-dir" in args:
        position = args.index("--runtime-dir")
        runtime = Path(args[position + 1])
    title = " ".join(arg for arg in args if not arg.startswith("--") and arg != str(runtime)) or "Kısa Bölüm"
    manifest = build(runtime, title)
    print(f"ürün: {manifest['folder']}")
    print("doğrulama:", "temiz" if manifest["validated"] else manifest["problems"][:3])
    return 0 if manifest["validated"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
