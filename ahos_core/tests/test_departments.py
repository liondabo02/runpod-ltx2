from __future__ import annotations

import json

import pytest

from ahos.departments import (
    CapabilitySpec,
    DepartmentBook,
    DepartmentBookError,
    DepartmentSpec,
    WorkerSpec,
    ascii_fold,
    seed_department_specs,
    slugify,
)
from ahos.routing import DepartmentRoutingEngine


def _spec(department_id: str = "test-unit", name: str = "Test Unit") -> DepartmentSpec:
    return DepartmentSpec(
        department_id=department_id,
        name=name,
        mission="Prove that owner commands can register new departments.",
        capabilities=(
            CapabilitySpec(name=f"{department_id}.build", description="build things"),
            CapabilitySpec(name=f"{department_id}.review", description="review things"),
        ),
        workers=(
            WorkerSpec(
                worker_id=f"{department_id}-manager",
                name="Manager",
                role="department_manager",
                team_id=f"{department_id}-leadership",
                capabilities=frozenset({"planning", "build", "review"}),
                reports_to=None,
                authority_level="A",
            ),
            WorkerSpec(
                worker_id=f"{department_id}-builder",
                name="Builder",
                role="software_engineer",
                team_id=f"{department_id}-delivery",
                capabilities=frozenset({"build"}),
                reports_to=f"{department_id}-manager",
            ),
            WorkerSpec(
                worker_id=f"{department_id}-reviewer",
                name="Reviewer",
                role="qa_engineer",
                team_id=f"{department_id}-delivery",
                capabilities=frozenset({"review"}),
                reports_to=f"{department_id}-manager",
            ),
        ),
        keywords=("test", "deneme"),
        source="owner-command",
    )


def test_seeded_book_covers_the_virtual_workforce() -> None:
    book = DepartmentBook(seed=True)
    departments = book.all()

    assert len(departments) == 11
    assert {spec.department_id for spec in departments} == {
        "software",
        "quality",
        "research",
        "infrastructure",
        "data",
        "creative",
        "marketing",
        "sales",
        "finance",
        "operations",
        "support",
    }
    for spec in departments:
        assert spec.validate() is spec
        assert sum(worker.is_manager for worker in spec.workers) == 1
        assert spec.workers[0].worker_id.endswith("-01")


def test_seed_specs_are_validated_without_a_book() -> None:
    for spec in seed_department_specs():
        assert spec.source == "seed"
        assert spec.status == "active"
        assert spec.capabilities


def test_book_persists_departments_across_reopen(tmp_path) -> None:
    path = tmp_path / "departments.json"
    book = DepartmentBook(path)
    book.add(_spec("pixel-studio", "Pixel Studio"))

    reopened = DepartmentBook(path)
    restored = reopened.require("pixel-studio")

    assert restored.name == "Pixel Studio"
    assert sorted(worker.worker_id for worker in restored.workers) == [
        "pixel-studio-builder",
        "pixel-studio-manager",
        "pixel-studio-reviewer",
    ]
    assert restored.created_at


def test_book_rejects_duplicate_department_ids() -> None:
    book = DepartmentBook(seed=True)

    with pytest.raises(DepartmentBookError, match="already exists"):
        book.add(_spec("software", "Software Again"))


def test_book_can_upgrade_a_seeded_department_in_place() -> None:
    book = DepartmentBook(seed=True)
    before = book.require("software")
    assert len(before.workers) == 2

    upgraded = book.add(_spec("software", "Software Company"), replace=True)

    assert upgraded.name == "Software Company"
    assert len(book.require("software").workers) == 3
    assert len(book.all()) == 11


def test_book_pause_keeps_the_definition_and_removes_it_from_routing() -> None:
    book = DepartmentBook(seed=True)
    book.pause("sales")

    assert book.require("sales").status == "paused"
    assert "sales" not in {spec.department_id for spec in book.active()}


def test_capability_registry_exposes_dynamic_departments() -> None:
    book = DepartmentBook(seed=True)
    book.add(_spec("pixel-studio", "Pixel Studio"))

    registry = book.capability_registry()
    engine = DepartmentRoutingEngine(registry)
    decision = engine.route_mission("m-1", "pixel studio build a sprite atlas")

    assert decision.primary is not None
    assert decision.primary.department == "pixel-studio"
    assert registry.capabilities_for("pixel-studio")[0].name.startswith("pixel-studio.")


def test_workforce_is_derived_from_the_book() -> None:
    book = DepartmentBook(seed=True)
    book.add(_spec("pixel-studio", "Pixel Studio"))

    workforce = book.workforce()

    assert len(workforce.all()) == 22 + 3
    profile = workforce.get("pixel-studio-manager").profile
    assert profile.department == "pixel-studio"
    assert profile.can_use_paid_ai is False


def test_department_spec_rejects_invalid_structures() -> None:
    with pytest.raises(DepartmentBookError, match="department_id"):
        _spec("Bad Id!")

    with pytest.raises(DepartmentBookError, match="exactly one department_manager"):
        DepartmentSpec(
            department_id="no-manager",
            name="No Manager",
            mission="invalid",
            capabilities=(CapabilitySpec("no-manager.build", "build"),),
            workers=(
                WorkerSpec(
                    worker_id="worker",
                    name="Worker",
                    role="software_engineer",
                    team_id="team",
                    capabilities=frozenset({"build"}),
                    reports_to=None,
                ),
            ),
        )

    with pytest.raises(DepartmentBookError, match="not covered"):
        DepartmentSpec(
            department_id="uncovered",
            name="Uncovered",
            mission="invalid",
            capabilities=(CapabilitySpec("uncovered.missing", "missing"),),
            workers=(
                WorkerSpec(
                    worker_id="uncovered-manager",
                    name="Manager",
                    role="department_manager",
                    team_id="lead",
                    capabilities=frozenset({"planning"}),
                    reports_to=None,
                ),
            ),
        )


def test_department_spec_round_trips_through_json() -> None:
    spec = _spec("pixel-studio", "Pixel Studio")

    payload = json.loads(json.dumps(spec.to_dict()))

    assert DepartmentSpec.from_dict(payload) == spec


def test_slugify_and_ascii_fold_handle_turkish_text() -> None:
    assert ascii_fold("Çizgi Film Şirketi") == "cizgi film sirketi"
    assert slugify("Çizgi Film Şirketi") == "cizgi-film-sirketi"
    assert slugify("   ") == "department"


def test_keyword_score_prefers_multi_word_keywords() -> None:
    spec = _spec()

    assert spec.keyword_score("test the build") == 10
    assert spec.keyword_score("irrelevant") == 0

def test_synthesized_department_exposes_a_valid_business_unit_blueprint() -> None:
    from ahos.org_synthesis import synthesize_department

    spec = synthesize_department("çizgi film departmanı kur")
    blueprint = spec.to_business_unit_blueprint()

    assert blueprint.business_unit_id == spec.department_id
    assert blueprint.director_worker_id == spec.manager.worker_id
    assert blueprint.owner_controlled is True
    assert len(blueprint.workers) == len(spec.workers)
    assert len(blueprint.teams) == len({w.team_id for w in spec.workers})
    assert blueprint.owner_reserved_decisions


def test_seeded_departments_convert_to_business_units() -> None:
    book = DepartmentBook(seed=True)

    for spec in book.all():
        blueprint = spec.to_business_unit_blueprint()
        assert blueprint.director_worker_id == spec.manager.worker_id
