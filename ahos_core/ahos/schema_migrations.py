from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    apply: Callable[[dict[str, object]], dict[str, object]]


class MigrationPlan:
    def __init__(self, migrations: list[Migration]) -> None:
        versions = [m.version for m in migrations]
        if versions != sorted(versions) or len(set(versions)) != len(versions):
            raise ValueError("migration versions must be unique and ordered")
        self.migrations = tuple(migrations)

    def migrate(self, payload: dict[str, object], *, current_version: int, target_version: int) -> dict[str, object]:
        if target_version < current_version:
            raise ValueError("downgrade requires explicit rollback path")
        result = dict(payload)
        version = current_version
        for migration in self.migrations:
            if version < migration.version <= target_version:
                result = migration.apply(dict(result))
                version = migration.version
        if version != target_version:
            raise ValueError("target version not reachable")
        result["_schema_version"] = version
        return result
