from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .openhands_builder import BuilderResult, OpenHandsBuilder
from .orchestrator import MiniverseOrchestrator
from .policy import OwnerPolicy


@dataclass(frozen=True)
class ExecutionResult:
    task: str
    preflight_report: str
    builder: BuilderResult
    qa_report: str
    owner_approval_required: bool
    owner_approval_reasons: tuple[str, ...]


class MiniverseExecutionPipeline:
    """Analyze -> build in isolated workspace -> adversarial QA review.

    This class deliberately has no deploy/publish/RunPod action. It only coordinates
    analysis and local workspace changes. External or paid actions remain gated.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        policy: OwnerPolicy | None = None,
        orchestrator: MiniverseOrchestrator | None = None,
        builder: OpenHandsBuilder | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.policy = policy or OwnerPolicy()
        self.orchestrator = orchestrator or MiniverseOrchestrator(settings=self.settings, policy=self.policy)
        self.builder = builder or OpenHandsBuilder(settings=self.settings)

    async def execute(self, task: str, workspace: str | Path) -> ExecutionResult:
        workspace_path = Path(workspace).resolve()
        if not workspace_path.exists() or not workspace_path.is_dir():
            raise ValueError(f"Workspace does not exist: {workspace_path}")

        decision = self.policy.evaluate(task)
        preflight = await self.orchestrator.analyze(
            task
            + "\n\nPHASE: PREFLIGHT ONLY. Do not claim code was changed. Identify root cause evidence, "
            "safe implementation boundaries, exact tests, and approval gates."
        )

        if not decision.allowed:
            raise PermissionError(
                "Owner approval required before execution: " + "; ".join(decision.reasons)
            )

        builder_result = await asyncio.to_thread(self.builder.run, task, workspace_path)

        changed_files = "\n".join(builder_result.changed_files)
        tests_run = "\n".join(builder_result.tests_run)
        remaining_risks = "\n".join(builder_result.remaining_risks)
        qa_prompt = (
            "Review the completed isolated-workspace coding run below. Try to falsify it. Do not modify anything. "
            "Decide whether tests are sufficient, identify regressions or unsupported claims, and state whether it is "
            "safe to open a PR. Never authorize deployment, paid GPU execution, publishing, secrets, or destructive actions."
            f"\n\nORIGINAL TASK:\n{task}"
            f"\n\nPREFLIGHT REPORT:\n{preflight}"
            f"\n\nBUILDER SUMMARY:\n{builder_result.summary}"
            f"\n\nCHANGED FILES:\n{changed_files}"
            f"\n\nTESTS RUN:\n{tests_run}"
            f"\n\nROLLBACK:\n{builder_result.rollback}"
            f"\n\nREMAINING RISKS:\n{remaining_risks}"
        )
        qa_report = await self.orchestrator.analyze(qa_prompt)

        return ExecutionResult(
            task=task,
            preflight_report=preflight,
            builder=builder_result,
            qa_report=qa_report,
            owner_approval_required=not decision.allowed,
            owner_approval_reasons=tuple(decision.reasons),
        )
