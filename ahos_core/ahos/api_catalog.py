"""public-apis katalogu: yuzlerce ucretsiz API'yi aranabilir hale getirir.

Kaynak: https://github.com/public-apis/public-apis (MIT). Katalog bir *liste*dir;
saglayici degildir. Bu modul yalnizca listeyi okur ve filtreler.

Kurallar:
- Katalog yoksa arama bos doner ve nedenini soyler (sahte sonuc uretmez).
- Varsayilan filtre: HTTPS + kimlik dogrulama istemeyen uclar.
- Bu modul HICBIR ag cagrisi yapmaz; cagriyi yapan katman (egress muhafizi)
  ayrica denetlenir.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "public-apis.json"

_LINK = re.compile(r"\[(?P<name>[^\]]+)\]\((?P<url>[^)]+)\)")
_ROW = re.compile(r"^\|\s*(?P<name>\[[^\]]+\]\([^)]+\))\s*\|(?P<rest>.+)\|\s*$")


def parse_readme(text: str) -> list[dict]:
    """public-apis README markdown'ini kayit listesine cevirir (saf fonksiyon)."""

    entries: list[dict] = []
    category = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("### "):
            category = line[4:].strip()
            continue
        match = _ROW.match(line)
        if match is None:
            continue
        link = _LINK.search(match.group("name"))
        if link is None:
            continue
        cells = [cell.strip() for cell in match.group("rest").split("|")]
        if len(cells) < 4:
            continue
        description, auth, https, cors = cells[0], cells[1], cells[2], cells[3]
        entries.append(
            {
                "name": link.group("name").strip(),
                "url": link.group("url").strip(),
                "description": description.strip(),
                "category": category,
                "auth": auth.strip("` ").strip() or "No",
                "https": https.strip().lower() == "yes",
                "cors": cors.strip().lower(),
            }
        )
    return entries


def load(path: str | Path | None = None) -> list[dict]:
    target = Path(path) if path is not None else CATALOG_PATH
    if not target.is_file():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entries = payload.get("entries") if isinstance(payload, dict) else payload
    return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []


def search(
    query: str,
    *,
    category: str | None = None,
    https_only: bool = True,
    no_auth_only: bool = False,
    limit: int = 20,
    path: str | Path | None = None,
) -> dict:
    """Katalogda ara; sonuc ve neden bos oldugunu birlikte dondur."""

    entries = load(path)
    if not entries:
        return {
            "ok": False,
            "reason": "katalog yok: tools/build_public_api_catalog.py ile olustur",
            "results": [],
            "total": 0,
        }

    needle = (query or "").casefold().strip()
    picked = []
    for entry in entries:
        if https_only and not entry.get("https"):
            continue
        auth = str(entry.get("auth", "")).strip().lower()
        if no_auth_only and auth not in {"no", ""}:
            continue
        if category and str(entry.get("category", "")).casefold() != category.casefold():
            continue
        if needle and needle not in f"{entry.get('name', '')} {entry.get('description', '')} {entry.get('category', '')}".casefold():
            continue
        picked.append(entry)

    picked.sort(key=lambda e: (str(e.get("name", "")).casefold(),))
    return {
        "ok": True,
        "total": len(picked),
        "results": picked[: max(1, int(limit))],
        "catalog_size": len(entries),
    }


def stats(path: str | Path | None = None) -> dict:
    entries = load(path)
    categories = {str(e.get("category", "")) for e in entries if e.get("category")}
    no_auth = sum(1 for e in entries if str(e.get("auth", "")).strip().lower() in {"no", ""})
    https = sum(1 for e in entries if e.get("https"))
    return {
        "available": bool(entries),
        "entries": len(entries),
        "categories": len(categories),
        "no_auth": no_auth,
        "https": https,
    }
