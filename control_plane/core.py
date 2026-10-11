from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from litellm import acompletion

from .agents import AGENTS, AgentSpec
from .state import StateStore


PARALLEL_ROLES = ("github_scout", "builder", "qa_sre", "cost_security")


@dataclass(frozen=True)
class Policy:
    auto_publish: bool = False
    external_spend: bool = False
    destructive_actions: bool = False
    max_parallel_agents: int = 4

    def approval_reasons(self, task: str) -> list[str]:
        t = task.lower()
        reasons: list[str] = []
        paid = ("runpod", "gpu", "buy", "purchase", "payment", "spend", "billing")
        destructive = ("delete", "destroy", "drop", "remove volume", "force push", "overwrite production")
        publishing = ("publish", "post", "upload to youtube", "release production")
        if not self.external_spend and any(k in t for k in paid):
            reasons.append("paid/external-spend action")
        if not self.destructive_actions and any(k in t for k in destructive):
            reasons.append("destructive action")
        if not self.auto_publish and any(k in t for k in publishing):
            reasons.append("external publishing action")
        return reasons


class AgentRunner:
    async def run(self, spec: AgentSpec, task: str, context: str = "") -> str:
        model = os.getenv(spec.model_env)
        if not model:
            return f"UNCONFIGURED: environment variable {spec.model_env} is not set."
        response = await acompletion(
            model=model,
            messages=[
                {"role": "system", "content": spec.system_prompt},
                {"role": "user", "content": f"TASK:\n{task}\n\nSHARED CONTEXT:\n{context}"},
            ],
            temperature=spec.temperature,
            max_tokens=spec.max_tokens,
        )
        return response.choices[0].message.content or ""


class ControlPlane:
    def __init__(self, store: StateStore | None = None, policy: Policy | None = None) -> None:
        self.store = store or StateStore()
        self.policy = policy or Policy()
        self.runner = AgentRunner()
        self._sem = asyncio.Semaphore(self.policy.max_parallel_agents)

    async def _run_role(self, run_id: int, role: str, task: str, context: str) -> tuple[str, str]:
        async with self._sem:
            result = await self.runner.run(AGENTS[role], task, context)
            self.store.add_message(run_id, role, "analysis", result)
            return role, result

    async def execute(self, task: str, shared_context: str = "") -> str:
        run_id = self.store.create_run(task)
        approval = self.policy.approval_reasons(task)
        if approval:
            note = "OWNER APPROVAL REQUIRED BEFORE ACTION: " + ", ".join(approval)
            self.store.add_message(run_id, "policy", "approval_gate", note)
            shared_context = f"{shared_context}\n\nPOLICY GATE:\n{note}".strip()

        try:
            findings = await asyncio.gather(
                *(self._run_role(run_id, role, task, shared_context) for role in PARALLEL_ROLES)
            )
            packed = "\n\n".join(f"## {role}\n{text}" for role, text in findings)
            synthesis_prompt = (
                "Synthesize the four specialist reports into one execution plan. "
                "Do not invent evidence. Preserve policy gates. Give: verified facts, root cause, safest action, "
                "tests, rollback, and whether owner action is required."
            )
            final = await self.runner.run(
                AGENTS["supervisor"],
                f"{task}\n\n{synthesis_prompt}",
                packed,
            )
            self.store.add_message(run_id, "supervisor", "final", final)
            self.store.finish_run(run_id, "completed")
            return final
        except Exception as exc:
            self.store.add_message(run_id, "system", "error", repr(exc))
            self.store.finish_run(run_id, "failed")
            raise
