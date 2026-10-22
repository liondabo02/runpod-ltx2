"""Business delivery and company founding (non-code work)."""

from __future__ import annotations

from pathlib import Path

from ahos.business_delivery import build_deliverable, detect_kind, validate_deliverable
from ahos.company_foundry import found
from ahos.owner_console import build_default_console


def test_deliverable_has_all_required_sections() -> None:
    text = build_deliverable("Kafe açılışı için pazarlama planı", "Pazarlama Ajansı")

    ok, problems = validate_deliverable(text)

    assert ok is True, problems
    assert "## İş planı" in text and "## Riskler" in text


def test_validation_rejects_a_stub() -> None:
    ok, problems = validate_deliverable("# plan\nTODO\n")

    assert ok is False
    assert any("bölüm eksik" in problem for problem in problems)


def test_kind_detection() -> None:
    assert detect_kind("yıllık değerlendirme raporu hazırla") == "report"
    assert detect_kind("açılış kontrol listesi") == "checklist"
    assert detect_kind("pazarlama stratejisi") == "plan"


def test_found_creates_company_workers_and_deliverable(tmp_path) -> None:
    console = build_default_console(tmp_path)

    result = found(
        console.book,
        console.book.workforce(),
        tmp_path,
        "Kafe açılışı için pazarlama planı hazırla",
    )

    assert result.created is True
    assert result.workers, "şirket işçisiz kurulmamalı"
    assert Path(result.deliverable).is_file()
    assert result.validated is True
    charter = Path(result.charter)
    assert charter.is_file()
    assert "Misyon" in charter.read_text(encoding="utf-8")


def test_unknown_request_founds_a_company_through_the_console(tmp_path) -> None:
    console = build_default_console(tmp_path)

    result = console.handle("Kafe açılışı için pazarlama planı hazırla")

    assert result.status == "routed"
    assert "teslimat:" in result.message
    # Talep mevcut bir şirkete (pazarlama) uyuyorsa o şirket teslim eder;
    # uymuyorsa yeni şirket kurulur. Her iki durumda da iş belgesi yazılır.
    assert result.department_id
    deliverables = list((tmp_path / "companies").glob("*/plan.md"))
    assert deliverables, "iş belgesi yazılmalı"
