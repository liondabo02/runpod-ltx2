"""Experience, shared task records and whole-product packages."""

from __future__ import annotations

import json

from ahos import experience, product, tasks


def test_experience_keeps_evidence_and_retrieves_similar(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    experience.record(
        runtime,
        objective="Mipiluna için günlük hedef göstergesi ekle",
        department="oyun",
        success=True,
        changed_files=1,
        method="model-produce · küçük yama",
    )
    experience.record(
        runtime,
        objective="Mipiluna için haftalık rozet ekle",
        department="oyun",
        success=False,
        blocker="yama hedefi bulunamadı",
        method="doğrudan içerik yazma",
    )

    hits = experience.similar(runtime, "Mipiluna için aylık rozet ekle")
    block = experience.context(runtime, "Mipiluna rozet")

    assert hits and hits[0]["success"] is True
    assert "BAŞARILI" in block and "BAŞARISIZ" in block
    summary = experience.summary(runtime)
    assert summary["records"] == 2 and summary["success"] == 1


def test_task_record_is_shared_and_updates(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    tasks.update(
        runtime,
        "CMD-1",
        objective="Sahne listesini çıkar",
        department="creative",
        worker="designer",
        status="running",
        attempts=1,
    )
    tasks.update(runtime, "CMD-1", status="completed", output="1 dosya")

    row = tasks.get(runtime, "CMD-1")
    assert row is not None
    assert row["status"] == "completed"
    assert row["output"] == "1 dosya"
    assert row["worker"] == "designer"
    assert tasks.list_tasks(runtime)[0]["mission_id"] == "CMD-1"


def test_product_package_is_complete_and_validated(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    manifest = product.build(runtime, "Bölüm 1 — Taslak")

    assert manifest["validated"] is True, manifest["problems"]
    folder = tmp_path / "runtime" / "products"
    created = list(folder.rglob("senaryo.md"))
    assert created, "senaryo dosyası yazılmalı"
    text = created[0].read_text(encoding="utf-8")
    assert "## Logline" in text
    ok, problems = product.validate(created[0].parent)
    assert ok and not problems


def test_product_validation_catches_missing_file(tmp_path) -> None:
    folder = tmp_path / "paket"
    folder.mkdir()
    (folder / "senaryo.md").write_text("# Senaryo\n\n## Logline\nkısa", encoding="utf-8")

    ok, problems = product.validate(folder)

    assert ok is False
    assert any("eksik dosya" in item for item in problems)
