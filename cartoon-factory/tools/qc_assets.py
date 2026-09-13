from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config" / "assets.yaml").read_text(encoding="utf-8"))
    contract = cfg["asset_contract"]
    failures: list[str] = []
    checked = 0

    for char in cfg["characters"]:
        cid = char["id"]
        base = ROOT / "assets" / "characters" / cid
        required = [base / "reference" / f"{v}.png" for v in contract["required_views"]]
        required += [base / "faces" / f"{e}.png" for e in contract["required_emotions"]]
        required += [base / "poses" / f"{a}_three_quarter.png" for a in contract["required_actions"]]
        required += [base / "mouths" / f"{m}.png" for m in contract["mouth_shapes"]]
        for path in required:
            checked += 1
            if not path.exists() or path.stat().st_size < 1024:
                failures.append(str(path.relative_to(ROOT)))

    report = {
        "ok": not failures,
        "checked": checked,
        "missing_or_invalid": failures,
        "note": "This gate verifies the complete reusable character pack before episode rendering. Visual identity scoring can be attached after reference assets exist."
    }
    out = ROOT / "output" / "asset_qc.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(0 if report["ok"] else 2)


if __name__ == "__main__":
    main()
