"""V5 GÖREV 012: onaylı hedef → kuyruk, idempotent ve yetki korumalı."""
from __future__ import annotations

import pytest

from ahos import goal_intake
from ahos.autonomous_company import PersistentMissionQueue, QueueStatus

TASKS = [{"objective": "senaryo taslağı", "department": "creative"},
         {"objective": "teknik QA", "department": "quality"}]


def test_approved_goal_creates_real_tasks(tmp_path):
    result = goal_intake.intake(tmp_path, goal="Aden kısa film", tasks=TASKS,
                                approved_by="harun")
    assert result["approved_by"] == "harun"
    assert len(result["created"]) == 2
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    pending = [m for m in queue.list() if m.status is QueueStatus.PENDING]
    assert {m.mission_id for m in pending} == {row["mission_id"] for row in result["created"]}
    assert pending[0].objective and pending[0].primary_department


def test_second_intake_is_idempotent(tmp_path):
    goal_intake.intake(tmp_path, goal="Aden kısa film", tasks=TASKS, approved_by="harun")
    again = goal_intake.intake(tmp_path, goal="Aden kısa film", tasks=TASKS,
                               approved_by="harun")
    assert again["created"] == [] and len(again["skipped"]) == 2


def test_owner_approval_is_required(tmp_path):
    with pytest.raises(PermissionError):
        goal_intake.intake(tmp_path, goal="x", tasks=TASKS, approved_by="agent")
    with pytest.raises(PermissionError):
        goal_intake.intake(tmp_path, goal="x", tasks=TASKS, approved_by="")


def test_empty_goal_or_too_many_tasks_rejected(tmp_path):
    with pytest.raises(ValueError):
        goal_intake.intake(tmp_path, goal="", tasks=TASKS, approved_by="harun")
    with pytest.raises(ValueError):
        goal_intake.intake(tmp_path, goal="x", tasks=TASKS * 11, approved_by="harun")
