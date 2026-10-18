from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AdapterTrust(str, Enum):
    CORE = "core"
    REVIEWED_OPEN_SOURCE = "reviewed_open_source"
    EXPERIMENTAL = "experimental"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class AdapterSpec:
    name: str
    capability: str
    trust: AdapterTrust
    free_by_default: bool
    sandbox_required: bool
    network_required: bool
    can_modify_repo: bool
    owner_approval_for_external_action: bool
    notes: str = ""


class AdapterCatalog:
    """Capability catalog for locally installed/open-source tools.

    Registration is descriptive only: it does not execute a binary, import a
    package, enable network access, or grant repository write authority.
    """

    def __init__(self) -> None:
        self._items: dict[str, AdapterSpec] = {}

    def register(self, spec: AdapterSpec) -> None:
        if not spec.name.strip() or not spec.capability.strip():
            raise ValueError("name and capability are required")
        if spec.name in self._items:
            raise ValueError("duplicate adapter")
        if spec.trust is AdapterTrust.BLOCKED and spec.can_modify_repo:
            raise ValueError("blocked adapters cannot receive repository authority")
        self._items[spec.name] = spec

    def get(self, name: str) -> AdapterSpec | None:
        return self._items.get(name)

    def by_capability(self, capability: str) -> tuple[AdapterSpec, ...]:
        return tuple(
            sorted(
                (item for item in self._items.values() if item.capability == capability),
                key=lambda item: (item.trust.value, item.name),
            )
        )

    def execution_eligible(self, name: str) -> bool:
        item = self._items.get(name)
        return bool(item and item.trust in {AdapterTrust.CORE, AdapterTrust.REVIEWED_OPEN_SOURCE})

    def snapshot(self) -> tuple[AdapterSpec, ...]:
        return tuple(sorted(self._items.values(), key=lambda item: item.name))


def default_catalog() -> AdapterCatalog:
    catalog = AdapterCatalog()
    for spec in (
        AdapterSpec("codex", "coding", AdapterTrust.CORE, False, True, True, True, True),
        AdapterSpec("claude-code", "coding", AdapterTrust.REVIEWED_OPEN_SOURCE, False, True, True, True, True),
        AdapterSpec("antigravity", "coding", AdapterTrust.EXPERIMENTAL, True, True, True, True, True),
        AdapterSpec("openhands", "coding", AdapterTrust.REVIEWED_OPEN_SOURCE, True, True, True, True, True),
        AdapterSpec("ollama", "local_model", AdapterTrust.REVIEWED_OPEN_SOURCE, True, True, False, False, False),
        AdapterSpec("openrouter", "model_gateway", AdapterTrust.REVIEWED_OPEN_SOURCE, True, True, True, False, True),
        AdapterSpec("deepseek-harness", "coding", AdapterTrust.EXPERIMENTAL, False, True, True, True, True),
        AdapterSpec("ltx2", "video_generation", AdapterTrust.REVIEWED_OPEN_SOURCE, False, True, True, False, True),
        AdapterSpec("chatterbox", "voice", AdapterTrust.REVIEWED_OPEN_SOURCE, True, True, False, False, False),
        AdapterSpec("kokoro", "voice", AdapterTrust.REVIEWED_OPEN_SOURCE, True, True, False, False, False),
        AdapterSpec("openvoice", "voice", AdapterTrust.REVIEWED_OPEN_SOURCE, True, True, False, False, False),
    ):
        catalog.register(spec)
    return catalog
