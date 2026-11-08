from __future__ import annotations

import pytest

from ahos.departments import DepartmentBook, DepartmentBookError, DepartmentSpec
from ahos.org_synthesis import (
    DOMAIN_TEMPLATES,
    match_domain,
    next_available_id,
    synthesize_department,
)
from ahos.virtual_workforce import WorkerRole


def test_cartoon_studio_request_builds_a_full_org_chart() -> None:
    spec = synthesize_department("çizgi film departmanı kur")

    assert spec.department_id == "creative"
    assert spec.name == "Çizgi Film Stüdyosu"
    assert spec.source == "owner-command"
    assert len(spec.workers) == 15
    assert spec.validate() is spec

    teams = {worker.team_id.rsplit("-", 1)[-1] for worker in spec.workers}
    assert {"story", "art", "animation", "audio", "growth", "quality"} <= teams

    managers = [worker for worker in spec.workers if worker.is_manager]
    assert len(managers) == 1
    assert managers[0].reports_to is None

    # every specialist ultimately reports to the manager
    by_id = {worker.worker_id: worker for worker in spec.workers}
    for worker in spec.workers:
        if worker.is_manager:
            continue
        seen: set[str] = set()
        current = worker
        while current.reports_to is not None:
            assert current.worker_id not in seen
            seen.add(current.worker_id)
            current = by_id[current.reports_to]
        assert current.is_manager


def test_software_company_request_builds_engineering_teams() -> None:
    spec = synthesize_department("yazılım şirketi kur")

    assert spec.department_id == "software"
    assert spec.name == "Yazılım Şirketi"
    capabilities = {worker_capability for worker in spec.workers for worker_capability in worker.capabilities}
    assert {"python", "backend", "testing", "deployment"} <= capabilities

    roles = {worker.role for worker in spec.workers}
    assert WorkerRole.SOFTWARE_ENGINEER.value in roles
    assert WorkerRole.QA_ENGINEER.value in roles


def test_unknown_domain_falls_back_to_a_generic_department() -> None:
    spec = synthesize_department("el yapımı sabun üretimi organize et")

    assert spec.department_id == "genel"
    assert spec.name == "Genel İş Departmanı"
    assert spec.validate() is spec


def test_domain_matching_prefers_the_most_specific_keywords() -> None:
    assert match_domain("çizgi film stüdyosu kur").domain_id == "cizgi-film"
    assert match_domain("e-ticaret mağazası aç").domain_id == "e-ticaret"
    assert match_domain("yazılım şirketi kur").domain_id == "yazilim"
    assert match_domain("alakasız bir istek") is None


def test_every_known_template_produces_a_valid_department() -> None:
    for template in DOMAIN_TEMPLATES:
        spec = synthesize_department(
            template.name,
            domain=template,
            department_id=f"{template.domain_id}-probe",
        )
        assert spec.validate() is spec
        assert len(spec.workers) % 2 == 1  # manager + lead/specialist pairs
        assert spec.keywords


def test_capabilities_are_covered_by_workers() -> None:
    spec = synthesize_department("çizgi film departmanı kur")
    covered = {capability for worker in spec.workers for capability in worker.capabilities}

    for capability in spec.capabilities:
        assert capability.name.rsplit(".", 1)[-1] in covered


def test_explicit_department_id_is_honoured() -> None:
    spec = synthesize_department("çizgi film kur", department_id="cizgi-film-2")

    assert spec.department_id == "cizgi-film-2"
    assert all(worker.worker_id.startswith("cizgi-film-2-") for worker in spec.workers)


def test_next_available_id_appends_a_numeric_suffix() -> None:
    book = DepartmentBook(seed=True)

    assert next_available_id(book, "pixel") == "pixel"
    book.add(synthesize_department("çizgi film kur", department_id="cizgi-film"))
    assert next_available_id(book, "cizgi-film") == "cizgi-film-2"


def test_synthesized_department_rejects_invalid_ids() -> None:
    with pytest.raises(DepartmentBookError, match="department_id"):
        synthesize_department("yazılım şirketi kur", department_id="Bad Id!")
