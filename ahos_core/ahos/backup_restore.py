from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class BackupRecord:
    source: str
    backup: str
    sha256: str
    created_at: str


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class BackupManager:
    def __init__(self, backup_dir: str | Path) -> None:
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def backup_file(self, source: str | Path) -> BackupRecord:
        src = Path(source)
        if not src.is_file():
            raise FileNotFoundError(src)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = self.backup_dir / f"{src.name}.{stamp}.bak"
        shutil.copy2(src, target)
        return BackupRecord(str(src), str(target), _sha256(target), datetime.now(timezone.utc).isoformat())

    def verify(self, record: BackupRecord) -> bool:
        path = Path(record.backup)
        return path.is_file() and _sha256(path) == record.sha256

    def plan_restore(self, record: BackupRecord, destination: str | Path) -> dict[str, object]:
        return {
            "source_backup": record.backup,
            "destination": str(destination),
            "sha256": record.sha256,
            "requires_owner_approval": True,
            "destructive_if_destination_exists": Path(destination).exists(),
            "execution_performed": False,
        }
