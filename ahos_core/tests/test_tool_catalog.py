from __future__ import annotations

from pathlib import Path

import pytest

from ahos.tool_catalog import CatalogError, load_catalog, render_catalog_report

CATALOG = """version: 1
policy: ../security/policy.yaml
tools:
  - id: openhands
    repo: OpenHands/OpenHands
    category: coding-agent
    license: MIT
    approved: true
    role: autonomous software development
  - id: cline
    repo: cline/cline
    category: ide-agent
    license: Apache-2.0
    approved: false
    role: IDE agent
"""

POLICY = """version: 1
mode: safe-auto-discovery
execution:
  new_repositories: quarantine
promotion:
  require_manual_approval: true
"""


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "foundry"
    (root / "catalog").mkdir(parents=True)
    (root / "security").mkdir()
    (root / "catalog" / "tools.yaml").write_text(CATALOG, encoding="utf-8")
    (root / "security" / "policy.yaml").write_text(POLICY, encoding="utf-8")
    return root


def test_catalog_loads_tools_and_policy(tmp_path) -> None:
    root = _repo(tmp_path)

    catalog = load_catalog(root / "catalog" / "tools.yaml")

    assert len(catalog.tools) == 2
    assert [tool.tool_id for tool in catalog.approved] == ["openhands"]
    assert catalog.categories == ("coding-agent", "ide-agent")
    assert catalog.policy["mode"] == "safe-auto-discovery"
    assert "2 araç" in catalog.summary()


def test_catalog_resolves_relative_policy(tmp_path) -> None:
    root = _repo(tmp_path)

    catalog = load_catalog(root / "catalog" / "tools.yaml")

    execution = catalog.policy.get("execution")
    assert isinstance(execution, dict)
    assert execution["new_repositories"] == "quarantine"


def test_missing_catalog_raises(tmp_path) -> None:
    with pytest.raises(CatalogError):
        load_catalog(tmp_path / "yok.yaml")


def test_broken_catalog_raises(tmp_path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("- sadece liste\n", encoding="utf-8")

    with pytest.raises(CatalogError):
        load_catalog(path)


def test_report_contains_table_and_policy(tmp_path) -> None:
    root = _repo(tmp_path)
    catalog = load_catalog(root / "catalog" / "tools.yaml")

    report = render_catalog_report(catalog)

    assert "Araç Kataloğu" in report
    assert "`openhands`" in report
    assert "safe-auto-discovery" in report
    assert "quarantine" in report
