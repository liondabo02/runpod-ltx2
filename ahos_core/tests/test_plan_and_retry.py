from __future__ import annotations

from pathlib import Path

from ahos.plan_mode import build_plan, validate_plan
from ahos.retry_policy import backoff, decide, plan


def test_plan_finds_real_target(tmp_path) -> None:
    (tmp_path / "www").mkdir()
    (tmp_path / "www" / "a.js").write_text("// x\n", encoding="utf-8")

    plan_obj = build_plan(tmp_path, "www/a.js dosyasına yorum ekle")

    assert plan_obj.executable is True
    kinds = [step.kind for step in plan_obj.steps]
    assert "read" in kinds and "edit" in kinds and "verify" in kinds


def test_plan_reports_missing_target(tmp_path) -> None:
    plan_obj = build_plan(tmp_path, "www/yok.js dosyasına yorum ekle")

    assert plan_obj.executable is False
    assert any("hedef yok" in problem for problem in plan_obj.problems)


def test_plan_without_target_is_not_executable(tmp_path) -> None:
    plan_obj = build_plan(tmp_path, "oyunu güzelleştir")

    assert plan_obj.executable is False


def test_plan_resolves_file_in_subdirectory(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "b.css").write_text("body{}\n", encoding="utf-8")

    plan_obj = build_plan(tmp_path, "b.css dosyasına renk ekle")

    assert plan_obj.executable is True
    assert any(step.path == "src/b.css" for step in plan_obj.steps)


def test_validate_plan_detects_deleted_file(tmp_path) -> None:
    (tmp_path / "a.js").write_text("// x\n", encoding="utf-8")
    plan_obj = build_plan(tmp_path, "a.js dosyasına yorum ekle")
    (tmp_path / "a.js").unlink()

    ok, problems = validate_plan(plan_obj, tmp_path)

    assert ok is False
    assert any("dosyası yok" in problem for problem in problems)


def test_backoff_grows_and_caps() -> None:
    assert backoff(1) == 30
    assert backoff(2) == 60
    assert backoff(3) == 120
    assert backoff(10) == 900


def test_decide_retries_worker_failure() -> None:
    decision = decide("worker_failed", 1)

    assert decision.retry is True
    assert decision.delay_seconds == 30
    assert decision.escalate is False


def test_decide_escalates_after_three() -> None:
    decision = decide("worker_failed", 3)

    assert decision.retry is False
    assert decision.escalate is True


def test_decide_refuses_fatal_cause() -> None:
    decision = decide("acceptance_failed", 1)

    assert decision.retry is False
    assert decision.escalate is False


def test_plan_dict_shape() -> None:
    payload = plan(None, "model_unavailable", 2)

    assert payload["retry"] is True
    assert payload["delay_seconds"] == 60
