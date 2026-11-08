import json
from types import SimpleNamespace
import pytest
from openhands.sdk.tool.builtins.finish import FinishTool, FinishAction

from miniverse.openhands_builder import parse_builder_finish


def test_finish_tool_is_created_and_result_is_parsed() -> None:
    tools = FinishTool.create()
    assert len(tools) == 1
    data = dict(change_summary="fixed", tests_run=["unit tests passed"],
                changed_files=["solution.py"], rollback="restore backup", remaining_risks=[])
    event = SimpleNamespace(action=FinishAction(message=json.dumps(data)))
    assert parse_builder_finish([SimpleNamespace(), event]).changed_files == ["solution.py"]


def test_missing_or_invalid_finish_fails_closed() -> None:
    with pytest.raises(RuntimeError):
        parse_builder_finish([])
    with pytest.raises(ValueError):
        parse_builder_finish([SimpleNamespace(action=FinishAction(message="finished"))])
