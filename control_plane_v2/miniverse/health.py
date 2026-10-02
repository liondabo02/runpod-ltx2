from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def write_heartbeat(path: str | Path, *, owner: str, state: str) -> None:
    heartbeat = Path(path)
    heartbeat.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "owner": owner,
        "state": state,
        "timestamp": time.time(),
    }
    tmp = heartbeat.with_suffix(heartbeat.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    tmp.replace(heartbeat)


def check_heartbeat(path: str | Path, *, max_age_seconds: float) -> dict[str, object]:
    heartbeat = Path(path)
    if not heartbeat.exists():
        raise RuntimeError(f"Heartbeat file missing: {heartbeat}")
    payload = json.loads(heartbeat.read_text(encoding="utf-8"))
    timestamp = float(payload["timestamp"])
    age = max(0.0, time.time() - timestamp)
    if age > max_age_seconds:
        raise RuntimeError(
            f"Worker heartbeat stale: age={age:.1f}s max={max_age_seconds:.1f}s"
        )
    payload["age_seconds"] = age
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Miniverse worker health probe")
    parser.add_argument("--path", default="/var/lib/miniverse/worker-heartbeat.json")
    parser.add_argument("--max-age-seconds", type=float, default=90.0)
    args = parser.parse_args()
    try:
        payload = check_heartbeat(args.path, max_age_seconds=args.max_age_seconds)
    except Exception as exc:
        print(f"UNHEALTHY: {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc
    print("HEALTHY " + json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
