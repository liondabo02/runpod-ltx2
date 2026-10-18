from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field
from openhands.sdk import Agent, Conversation, LLM, Tool
from openhands.sdk.tool import register_tool
from openhands.sdk.tool.builtins.finish import FinishAction, FinishTool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool
from openhands.tools.terminal import TerminalTool

from .config import Settings


class BuilderFinish(BaseModel):
    change_summary: str = Field(description="What was changed and why.")
    tests_run: list[str] = Field(description="Exact tests/commands run and their outcomes.")
    changed_files: list[str] = Field(description="Files changed inside the isolated workspace.")
    rollback: str = Field(description="How to revert the change safely.")
    remaining_risks: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class BuilderResult:
    summary: str
    tests_run: tuple[str, ...]
    changed_files: tuple[str, ...]
    rollback: str
    remaining_risks: tuple[str, ...]
    estimated_cost_usd: float


def parse_builder_finish(events) -> BuilderFinish:
    for event in reversed(list(events)):
        action = getattr(event, "action", None)
        if isinstance(action, FinishAction):
            return BuilderFinish.model_validate_json(action.message)
    raise RuntimeError("OpenHands builder finished without a structured FinishTool result")


register_tool("FinishTool", FinishTool)


class OpenHandsBuilder:
    """Coding worker for isolated workspaces. Never point this at production directly."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()

    def run(self, task: str, workspace: str | Path) -> BuilderResult:
        workspace_path = Path(workspace).resolve()
        if not workspace_path.exists() or not workspace_path.is_dir():
            raise ValueError(f"Workspace does not exist: {workspace_path}")

        llm = LLM(
            model=self.settings.openhands_model,
            api_key=self.settings.llm_api_key or self.settings.openai_api_key,
            base_url=self.settings.llm_base_url,
        )
        agent = Agent(
            llm=llm,
            tools=[
                Tool(name=TerminalTool.name),
                Tool(name=FileEditorTool.name),
                Tool(name=TaskTrackerTool.name),
                Tool(name="FinishTool"),
            ],
            include_default_tools=["ThinkTool"],
        )
        conversation = Conversation(
            agent=agent, workspace=str(workspace_path),
            max_iteration_per_run=self.settings.openhands_max_iterations,
        )
        conversation.send_message(
            "Work only inside this isolated workspace. Do not modify production, credentials, billing, volumes, "
            "or external systems. Make the smallest coherent reversible change. Inspect the repository first, run "
            "the most relevant tests, and use FinishTool only after you can report exact changed files, test results, "
            "rollback instructions, and remaining risks. Set FinishTool.message to a JSON object with fields "
            "change_summary, tests_run (list), changed_files (list), rollback, remaining_risks (list).\n\nTASK:\n" + task
        )
        conversation.run()

        finish = parse_builder_finish(conversation.state.events)

        metrics = conversation.conversation_stats.get_combined_metrics()
        cost = float(metrics.accumulated_cost or 0.0)
        return BuilderResult(
            summary=finish.change_summary,
            tests_run=tuple(finish.tests_run),
            changed_files=tuple(finish.changed_files),
            rollback=finish.rollback,
            remaining_risks=tuple(finish.remaining_risks),
            estimated_cost_usd=cost,
        )
