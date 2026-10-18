from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
import os
import uuid


@dataclass(frozen=True, slots=True)
class Checkpoint:
    task_id: str
    step: str
    state: dict[str, object]
    sequence: int


class CheckpointStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, checkpoint: Checkpoint) -> None:
        if checkpoint.sequence < 0:
            raise ValueError("sequence must be nonnegative")
        temp = self.path.with_name(f"{self.path.name}.{uuid.uuid4().hex}.tmp")
        temp.write_text(json.dumps(asdict(checkpoint), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, self.path)

    def load(self) -> Checkpoint | None:
        if not self.path.is_file():
            return None
        return Checkpoint(**json.loads(self.path.read_text(encoding="utf-8")))
