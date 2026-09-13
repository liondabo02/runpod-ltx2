from __future__ import annotations

from pathlib import Path

from openhands.sdk import Agent, Conversation, LLM, Tool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool
from openhands.tools.terminal import TerminalTool

from .config import Settings


class OpenHandsBuilder:
    """Coding worker for isolated workspaces. Never point this at production directly."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()

    def run(self, task: str, workspace: str | Path) -> str:
        workspace_path = Path(workspace).resolve()
        llm = LLM(
            model=self.settings.openhands_model,
            api_key=self.settings.llm_api_key or self.settings.openai_api_key,
        )
        agent = Agent(
            llm=llm,
            tools=[
                Tool(name=TerminalTool.name),
                Tool(name=FileEditorTool.name),
                Tool(name=TaskTrackerTool.name),
            ],
        )
        conversation = Conversation(agent=agent, workspace=str(workspace_path))
        conversation.send_message(
            "Work only inside this isolated workspace. Do not modify production or secrets. "
            "Create the smallest coherent change, run tests, and leave a clear summary with rollback instructions.\n\n"
            + task
        )
        conversation.run()
        return "OpenHands builder run completed; inspect workspace diff and tests before any merge."
