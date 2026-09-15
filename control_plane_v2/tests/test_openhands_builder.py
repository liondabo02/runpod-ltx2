from openhands.sdk import Tool

from miniverse.openhands_builder import BuilderFinish


def test_finish_response_schema_is_accepted_by_openhands() -> None:
    tool = Tool(name="FinishTool", params={"response_schema": BuilderFinish})
    assert tool is not None
