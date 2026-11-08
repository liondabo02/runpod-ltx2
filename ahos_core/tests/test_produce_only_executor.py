from __future__ import annotations

from ahos.owner_console import _produce_only_executor


class _Item:
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id


def _exec(name: str):
    def _run(item, worker_id):
        return f"{name}:{item.task_id.rsplit(':', 1)[-1]}"

    return _run


def test_produce_only_routes_brief_and_review_to_the_deterministic_worker() -> None:
    executor = _produce_only_executor(_exec("model"), _exec("det"))

    assert executor(_Item("d:m1:brief"), "w") == "det:brief"
    assert executor(_Item("d:m1:produce"), "w") == "model:produce"
    assert executor(_Item("d:m1:review"), "w") == "det:review"


def test_other_steps_stay_with_the_model_executor() -> None:
    executor = _produce_only_executor(_exec("model"), _exec("det"))

    assert executor(_Item("d:m1:deploy"), "w") == "model:deploy"
