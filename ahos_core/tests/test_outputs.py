from __future__ import annotations

import json
from pathlib import Path

import pytest

from ahos.autonomous_company import PersistentMissionQueue
from ahos.outputs import (
    build_output_index,
    markdown_to_html,
    render_document_page,
    render_outputs_page,
    resolve_output_file,
)


def _write_mission_artifacts(root: Path, mission_id: str, steps: dict[str, str]) -> None:
    for step, content in steps.items():
        directory = root / f"{mission_id}_{step}"
        directory.mkdir(parents=True)
        (directory / "deliverable.md").write_text(content, encoding="utf-8")


@pytest.fixture()
def artifacts(tmp_path) -> Path:
    root = tmp_path / "artifacts"
    root.mkdir()
    _write_mission_artifacts(
        root,
        "CMD-1-oyun-gelistir",
        {
            "brief": "# Analiz\n\nOyun incelendi.\n",
            "produce": "# Plan\n\n| Adım | Süre |\n| --- | --- |\n| 1 | 2 gün |\n",
            "review": "# QA\n\nGeçti.\n",
        },
    )
    security = root / "CMD-2-guvenlik-tara_brief"
    security.mkdir()
    (security / "SECURITY_REPORT.md").write_text("# Rapor\n\n3 bulgu\n", encoding="utf-8")
    (security / "findings.json").write_text(json.dumps({"ok": False}), encoding="utf-8")
    return root


def test_index_groups_steps_by_mission(artifacts: Path) -> None:
    outputs = build_output_index(artifacts)

    assert len(outputs) == 2
    game = next(item for item in outputs if item.mission_id == "CMD-1-oyun-gelistir")
    assert set(game.steps) == {"brief", "produce", "review"}
    assert len(game.files) == 3  # one deliverable per step directory

    security = next(item for item in outputs if item.mission_id == "CMD-2-guvenlik-tara")
    names = {item.name for item in security.files}
    assert {"SECURITY_REPORT.md", "findings.json"} <= names
    assert security.steps == ("brief",)


def test_index_enriches_from_queue(artifacts: Path, tmp_path) -> None:
    queue = PersistentMissionQueue(tmp_path / "queue.db")
    queue.enqueue(
        mission_id="CMD-1-oyun-gelistir",
        objective="Mipiluna oyununu geliştir",
        primary_department="oyun",
    )

    outputs = build_output_index(artifacts, queue)
    game = next(item for item in outputs if item.mission_id == "CMD-1-oyun-gelistir")

    assert game.department == "oyun"
    assert game.objective == "Mipiluna oyununu geliştir"
    assert game.status == "pending"


def test_index_ignores_empty_directories(tmp_path) -> None:
    root = tmp_path / "artifacts"
    (root / "CMD-3-bos_brief").mkdir(parents=True)

    assert build_output_index(root) == ()


def test_resolve_output_file_blocks_traversal(artifacts: Path) -> None:
    with pytest.raises(ValueError):
        resolve_output_file(artifacts, "..", "deliverable.md")

    with pytest.raises(FileNotFoundError):
        resolve_output_file(artifacts, "CMD-1-oyun-gelistir_brief", "yok.md")

    resolved = resolve_output_file(
        artifacts, "CMD-1-oyun-gelistir_brief", "deliverable.md"
    )
    assert resolved.exists()


def test_markdown_renderer_handles_tables_and_headings() -> None:
    html = markdown_to_html("# Başlık\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n")

    assert "<h1>Başlık</h1>" in html
    assert "<table>" in html
    assert "<td>1</td>" in html


def test_markdown_renderer_escapes_html() -> None:
    html = markdown_to_html("script <script>alert(1)</script>")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_outputs_page_lists_missions_and_links(artifacts: Path) -> None:
    page = render_outputs_page(build_output_index(artifacts))

    assert "Çıktılar ve Teslimatlar" in page
    assert "/outputs/view?dir=" in page
    assert "CMD-1-oyun-gelistir" in page


def test_outputs_page_includes_project_documents(artifacts: Path) -> None:
    page = render_outputs_page(
        build_output_index(artifacts),
        [{"project_id": "mipiluna", "name": "Mipiluna", "department_id": "oyun", "files": ["INTEGRATION_PLAN.md"]}],
    )

    assert "Projeler" in page
    assert "/outputs/project?project=mipiluna" in page


def test_document_page_renders_markdown(artifacts: Path) -> None:
    document = artifacts / "CMD-1-oyun-gelistir_brief" / "deliverable.md"

    page = render_document_page("Analiz", document)

    assert "AHOS" in page
    assert "<h1>Analiz</h1>" in page

def test_markdown_renderer_supports_blockquotes() -> None:
    html = markdown_to_html("> Dikkat: bu bir uyarıdır\n> ikinci satır\n\nNormal paragraf")

    assert "<blockquote>" in html
    assert "Dikkat: bu bir uyarıdır" in html
    assert "<br>" in html
    assert "Normal paragraf" in html
    assert "</blockquote>" in html


def test_blockquote_content_is_escaped() -> None:
    html = markdown_to_html("> <script>alert(1)</script>")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
