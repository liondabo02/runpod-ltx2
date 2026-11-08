"""public-apis README'sini JSON kataoga cevir (ag gerekmez).

Kullanim:
    python tools/build_public_api_catalog.py <README.md> [-o ahos_core/data/public-apis.json]

README'yi indirmek icin (ag erisimi olan bir makinede):
    curl -L https://raw.githubusercontent.com/public-apis/public-apis/master/README.md -o public-apis.md
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ahos.api_catalog import parse_readme  # noqa: E402

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "ahos_core" / "data" / "public-apis.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="public-apis katalog olusturucu")
    parser.add_argument("readme", help="public-apis README.md yolu")
    parser.add_argument("-o", "--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)

    source = Path(args.readme)
    if not source.is_file():
        print(json.dumps({"ok": False, "reason": f"README bulunamadi: {source}"}))
        return 2

    entries = parse_readme(source.read_text(encoding="utf-8"))
    if not entries:
        print(json.dumps({"ok": False, "reason": "ayristirilacak kayit yok"}))
        return 1

    payload = {
        "source": "https://github.com/public-apis/public-apis",
        "license": "MIT",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(entries),
        "entries": entries,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": True, "entries": len(entries), "out": str(out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
