from __future__ import annotations

import hashlib
import json


class IdempotencyKeys:
    @staticmethod
    def make(namespace: str, payload: dict[str, object]) -> str:
        if not namespace.strip():
            raise ValueError("namespace required")
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return f"{namespace}:{hashlib.sha256(raw).hexdigest()}"
