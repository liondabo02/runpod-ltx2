from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:  # PyYAML is bundled with the worker venv; degrade gracefully without it
    import yaml
except Exception:  # pragma: no cover - optional dependency
    yaml = None


class CatalogError(ValueError):
    """Raised when a tool catalog or policy cannot be read."""


@dataclass(frozen=True, slots=True)
class Tool:
    tool_id: str
    repo: str = ""
    category: str = ""
    license: str = ""
    approved: bool = False
    execution: str = ""
    role: str = ""
    connect: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.tool_id,
            "repo": self.repo,
            "category": self.category,
            "license": self.license,
            "approved": self.approved,
            "execution": self.execution,
            "role": self.role,
            "connect": self.connect,
        }


@dataclass(frozen=True, slots=True)
class Catalog:
    source: Path
    tools: tuple[Tool, ...] = ()
    policy: dict[str, object] = field(default_factory=dict)

    @property
    def approved(self) -> tuple[Tool, ...]:
        return tuple(tool for tool in self.tools if tool.approved)

    @property
    def categories(self) -> tuple[str, ...]:
        return tuple(sorted({tool.category for tool in self.tools if tool.category}))

    def summary(self) -> str:
        return (
            f"{len(self.tools)} araç ({len(self.approved)} onaylı), "
            f"{len(self.categories)} kategori, "
            f"politika modu: {self.policy.get('mode', '-')}"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "source": str(self.source),
            "tools": [tool.to_dict() for tool in self.tools],
            "policy": self.policy,
        }


def _require_yaml() -> None:
    if yaml is None:
        raise CatalogError("PyYAML bulunamadı; katalog okunamadı")


def _load_yaml(path: Path) -> dict[str, object]:
    _require_yaml()
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:  # type: ignore[union-attr]
        raise CatalogError(f"okunamadı: {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CatalogError(f"beklenen YAML sözlüğü değil: {path.name}")
    return payload


def load_catalog(
    catalog_path: str | Path,
    policy_path: str | Path | None = None,
) -> Catalog:
    """Load a tool catalog (tools.yaml) and its policy file."""

    path = Path(catalog_path)
    if not path.exists():
        raise CatalogError(f"katalog yok: {path}")

    payload = _load_yaml(path)
    policy: dict[str, object] = {}
    resolved_policy = Path(policy_path) if policy_path else path.parent / ".." / "security" / "policy.yaml"
    if resolved_policy.exists():
        policy = _load_yaml(resolved_policy)
    elif isinstance(payload.get("policy"), str):
        hinted = (path.parent / str(payload["policy"])).resolve()
        if hinted.exists():
            policy = _load_yaml(hinted)

    tools: list[Tool] = []
    for entry in payload.get("tools") or ():
        if not isinstance(entry, dict):
            continue
        tool_id = str(entry.get("id") or "").strip()
        if not tool_id:
            continue
        tools.append(
            Tool(
                tool_id=tool_id,
                repo=str(entry.get("repo") or ""),
                category=str(entry.get("category") or ""),
                license=str(entry.get("license") or ""),
                approved=bool(entry.get("approved", False)),
                execution=str(entry.get("execution") or ""),
                role=str(entry.get("role") or ""),
                connect=str(entry.get("connect") or ""),
            )
        )

    return Catalog(source=path, tools=tuple(tools), policy=policy)


def render_catalog_report(catalog: Catalog) -> str:
    lines = [
        "# Araç Kataloğu (Harun AI Foundry)",
        "",
        f"- **Kaynak:** `{catalog.source}`",
        f"- **Özet:** {catalog.summary()}",
        "",
        "| Araç | Kategori | Lisans | Onaylı | Rol |",
        "| --- | --- | --- | --- | --- |",
    ]
    for tool in catalog.tools:
        lines.append(
            f"| `{tool.tool_id}` | {tool.category or '-'} | {tool.license or '-'} | "
            f"{'evet' if tool.approved else 'hayır'} | {tool.role[:70]} |"
        )
    lines += ["", "## Politika", ""]
    if catalog.policy:
        for key in ("version", "mode"):
            if key in catalog.policy:
                lines.append(f"- **{key}:** {catalog.policy[key]}")
        for section in ("discovery", "execution", "promotion"):
            block = catalog.policy.get(section)
            if isinstance(block, dict):
                lines.append(f"- **{section}:**")
                for key, value in block.items():
                    lines.append(f"  - {key}: {value}")
    else:
        lines.append("- politika dosyası bulunamadı")
    lines.append("")
    return "\n".join(lines)
