from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from ahos.projects import (
    ProjectError,
    ProjectLink,
    ProjectRegistry,
    audit_project,
    build_integration_plan,
    detect_project_kind,
    import_project,
    project_id_for,
    render_audit,
    resolve_project_source,
)


@pytest.fixture()
def fake_project(tmp_path) -> Path:
    root = tmp_path / "Mipiluna-22"
    (root / "android" / "app").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "www").mkdir()
    (root / "index.html").write_text("<html><body>oyun</body></html>", encoding="utf-8")
    (root / "www" / "index.html").write_text("<html>oyun</html>", encoding="utf-8")
    (root / "family.js").write_text("// TODO: bolum ekle\nconst a = 1;\n", encoding="utf-8")
    (root / "README.md").write_text("# Mipiluna\n", encoding="utf-8")
    (root / "package.json").write_text(
        json.dumps({"name": "mipiluna", "scripts": {"build": "x", "test": "y"}}),
        encoding="utf-8",
    )
    (root / "android" / "app" / "build.gradle").write_text("android {}", encoding="utf-8")
    (root / "docs" / "TASARIM.md").write_text("# Tasarım\n", encoding="utf-8")
    (root / "assets").mkdir()
    (root / "assets" / "logo.png").write_bytes(b"\x89PNG")
    return root


def test_audit_project_collects_real_facts(fake_project: Path) -> None:
    audit = audit_project(fake_project, name="Mipiluna")

    assert audit.name == "Mipiluna"
    assert audit.file_count == 8
    assert audit.sizes_mb >= 0
    assert audit.has_android is True
    assert audit.has_git is False
    assert "www/index.html" in audit.entry_points
    assert "package.json" in audit.entry_points
    assert "README.md" in audit.entry_points
    assert "README.md" in audit.docs
    assert audit.todo_hits >= 1
    assert audit.web_root == "www"
    assert audit.npm_scripts == ("build", "test")
    assert set(audit.directories) == {"android", "assets", "docs", "www"}
    suffixes = dict(audit.extensions)
    assert suffixes[".js"] == 1
    assert suffixes[".html"] == 2


def test_audit_rejects_missing_directory(tmp_path) -> None:
    with pytest.raises(ProjectError):
        audit_project(tmp_path / "yok")


def test_detect_project_kind_for_capacitor_game(fake_project: Path) -> None:
    assert detect_project_kind(audit_project(fake_project)) == "capacitor-html5-game"


def test_registry_persists_links(tmp_path, fake_project: Path) -> None:
    path = tmp_path / "projects.json"
    registry = ProjectRegistry(path)
    link = ProjectLink(
        project_id="mipiluna",
        name="Mipiluna",
        path=fake_project,
        department_id="oyun",
        kind="capacitor-html5-game",
    )
    registry.link(link)

    reopened = ProjectRegistry(path)

    assert reopened.require("mipiluna").department_id == "oyun"
    assert reopened.for_department("oyun")[0].project_id == "mipiluna"
    assert json.loads(path.read_text(encoding="utf-8"))["projects"][0]["name"] == "Mipiluna"


def test_registry_rejects_missing_project_path(tmp_path) -> None:
    registry = ProjectRegistry()

    with pytest.raises(ProjectError):
        registry.link(
            ProjectLink(
                project_id="x",
                name="X",
                path=tmp_path / "yok",
                department_id="oyun",
            )
        )


def test_import_project_from_zip(tmp_path) -> None:
    archive = tmp_path / "Mipiluna-22-Kaynak.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("index.html", "<html>ok</html>")
        handle.writestr("android/build.gradle", "android {}")

    target = import_project("Mipiluna", archive, tmp_path / "out")

    assert (target / "index.html").exists()
    assert (target / "android" / "build.gradle").exists()


def test_import_project_rejects_unsafe_zip_members(tmp_path) -> None:
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../evil.txt", "x")

    with pytest.raises(ProjectError):
        import_project("evil", archive, tmp_path / "out")


def test_import_project_is_idempotent(tmp_path) -> None:
    archive = tmp_path / "p.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("index.html", "<html></html>")

    first = import_project("p", archive, tmp_path / "out")
    second = import_project("p", archive, tmp_path / "out")

    assert first == second
    assert (second / "index.html").exists()


def test_resolve_project_source_prefers_newest_version(tmp_path) -> None:
    for version in (21, 22):
        (tmp_path / f"Mipiluna-{version}-Mobil-Kaynak.zip").write_bytes(b"zip")
    (tmp_path / "baska.zip").write_bytes(b"zip")

    resolved = resolve_project_source("Mipiluna", [tmp_path])

    assert resolved is not None
    assert "Mipiluna-22" in resolved.name


def test_project_id_slugifies_names() -> None:
    assert project_id_for("Mipiluna") == "mipiluna"
    assert project_id_for("Mipiluna 22 Oyun") == "mipiluna-22-oyun"


def test_integration_plan_contains_phases_and_team(tmp_path, fake_project: Path) -> None:
    from ahos.org_synthesis import synthesize_department

    spec = synthesize_department("oyun geliştirme departmanı kur")
    audit = audit_project(fake_project, name="Mipiluna")
    link = ProjectLink(
        project_id="mipiluna",
        name="Mipiluna",
        path=fake_project,
        department_id="oyun",
        kind="capacitor-html5-game",
    )

    plan = build_integration_plan(link, spec, audit)

    assert "# Mipiluna" in plan
    assert spec.name in plan
    assert "Envanter ve build doğrulama" in plan
    assert "Kabul kriterleri" in plan
    assert f"{spec.department_id}-quality-lead" in plan
    assert "TODO/FIXME" in plan

    audit_doc = render_audit(link, audit)
    assert "Proje Denetimi" in audit_doc
    assert str(audit.file_count) in audit_doc

def test_import_project_skips_heavy_directories(tmp_path) -> None:
    source = tmp_path / "src"
    (source / "app").mkdir(parents=True)
    (source / ".venv" / "lib").mkdir(parents=True)
    (source / "node_modules" / "pkg").mkdir(parents=True)
    (source / "app" / "main.py").write_text("print(1)\n", encoding="utf-8")
    (source / ".venv" / "lib" / "big.py").write_text("x\n", encoding="utf-8")
    (source / "node_modules" / "pkg" / "index.js").write_text("x\n", encoding="utf-8")

    target = import_project("src", source, tmp_path / "out")

    assert (target / "app" / "main.py").exists()
    assert not (target / ".venv").exists()
    assert not (target / "node_modules").exists()


def test_zip_import_skips_heavy_directories(tmp_path) -> None:
    archive = tmp_path / "p.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("app/main.py", "print(1)")
        handle.writestr(".venv/lib/big.py", "x")

    target = import_project("p", archive, tmp_path / "z")

    assert (target / "app" / "main.py").exists()
    assert not (target / ".venv").exists()
