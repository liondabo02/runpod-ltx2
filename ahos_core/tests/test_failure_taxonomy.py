from __future__ import annotations

from ahos.failure_analytics import CAUSES, classify_error, classify_mission


def _row(message: str) -> dict:
    return {"message": message}


def test_project_lock_is_classified() -> None:
    assert classify_error(_row("proje kilidi: sahibi CMD-x (pid 123)")) == "project_lock"


def test_executor_missing_is_classified() -> None:
    assert classify_error(_row("executor_unavailable: Üretim yürütücüsü bağlı değil")) == "executor_missing"


def test_target_missing_is_classified() -> None:
    assert classify_error(_row("yama için dosya yok: www/style.css")) == "target_missing"


def test_model_timeout_is_classified() -> None:
    assert classify_error(_row("qwen2.5-coder:7b: TimeoutError")) == "model_unavailable"


def test_empty_delivery_is_classified() -> None:
    assert classify_error(_row("teslimat yok: 0 dosya değişti")) == "no_delivery"


def test_qa_failure_is_classified() -> None:
    assert classify_error(_row("QA failed: kabul testi düştü")) == "acceptance_failed"


def test_mission_timeout_is_classified() -> None:
    assert classify_error(_row("timeout: görev 600s sınırını aştı; iptal DOĞRULANAMADI")) == "mission_timeout"


def test_worker_failure_is_classified() -> None:
    assert classify_error(_row("mission blocked at step produce: worker execution failed")) == "worker_failed"


def test_unknown_message_stays_other() -> None:
    assert classify_error(_row("açıklanamayan bir durum")) == "other"


def test_every_cause_has_a_label() -> None:
    for key in (
        "no_delivery", "acceptance_failed", "model_unavailable", "claim_blocked",
        "project_lock", "executor_missing", "target_missing", "worker_failed", "mission_timeout", "cancelled", "other",
    ):
        assert key in CAUSES


def test_mission_without_change_is_no_delivery() -> None:
    assert classify_mission({"status": "blocked", "changed_files": 0}) == "no_delivery"


def test_mission_with_change_but_blocked_is_acceptance() -> None:
    assert classify_mission({"status": "blocked", "changed_files": 2}) == "acceptance_failed"
