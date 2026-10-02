import ast
import inspect

from openhands.sdk import Tool

from miniverse import openhands_builder
from miniverse.openhands_builder import BuilderFinish


def test_finish_response_schema_is_accepted_by_openhands() -> None:
    tool = Tool(name="FinishTool", params={"response_schema": BuilderFinish})
    assert tool is not None


def test_conversation_uses_only_supported_constructor_keywords() -> None:
    tree = ast.parse(inspect.getsource(openhands_builder.OpenHandsBuilder.run))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Conversation"
    ]

    assert len(calls) == 1
    assert {keyword.arg for keyword in calls[0].keywords} == {"agent", "workspace"}
