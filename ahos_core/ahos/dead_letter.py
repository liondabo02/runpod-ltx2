from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class DeadLetter:
    item_id: str
    source_queue: str
    reason: str
    payload: dict[str, object]
    attempts: int
    created_at: str


class DeadLetterQueue:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def put(self, *, source_queue: str, reason: str, payload: dict[str, object], attempts: int) -> DeadLetter:
        if not source_queue or not reason:
            raise ValueError("source_queue and reason are required")
        if attempts < 0:
            raise ValueError("attempts must be nonnegative")
        item = DeadLetter(uuid.uuid4().hex, source_queue, reason[:1000], payload, attempts, _now())
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(item), ensure_ascii=False, sort_keys=True) + "\n")
        return item

    def read_all(self) -> tuple[DeadLetter, ...]:
        if not self.path.exists():
            return ()
        rows: list[DeadLetter] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            rows.append(DeadLetter(**raw))
        return tuple(rows)
