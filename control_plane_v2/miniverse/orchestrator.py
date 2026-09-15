from __future__ import annotations

from agent_framework import Agent, AgentResponse
from agent_framework.openai import OpenAIChatClient
from agent_framework.orchestrations import ConcurrentBuilder

from .config import Settings
from .policy import OwnerPolicy


ROLE_PROMPTS = {
    "scout": (
        "You are Miniverse GitHub Scout. Use primary sources, current releases, issues and exact versions. "
        "Separate verified facts from uncertainty. Never modify production."
    ),
    "qa": (
        "You are Miniverse QA/SRE. Try to falsify the proposed solution. Check compatibility, tests, rollback, "
        "idempotency, observability and end-to-end proof before declaring WORKING."
    ),
    "cost": (
        "You are Miniverse Cost & Security Guardian. Prefer existing infrastructure and free/static validation. "
        "Flag paid, destructive, credential, publishing, billing and legal actions for owner approval."
    ),
}


class MiniverseOrchestrator:
    def __init__(self, settings: Settings | None = None, policy: OwnerPolicy | None = None) -> None:
        self.settings = settings or Settings()
        self.policy = policy or OwnerPolicy()

    def _client(self, model: str) -> OpenAIChatClient:
        kwargs = {
            "model": model,
            "api_key": self.settings.openai_api_key or self.settings.llm_api_key,
        }
        if self.settings.llm_base_url:
            kwargs["base_url"] = self.settings.llm_base_url
        return OpenAIChatClient(**kwargs)

    async def analyze(self, task: str) -> str:
        decision = self.policy.evaluate(task)
        gate = ""
        if not decision.allowed:
            gate = "\n\nOWNER APPROVAL GATE:\n- " + "\n- ".join(decision.reasons)

        participants = [
            Agent(client=self._client(self.settings.scout_model), name="scout", instructions=ROLE_PROMPTS["scout"]),
            Agent(client=self._client(self.settings.qa_model), name="qa_sre", instructions=ROLE_PROMPTS["qa"]),
            Agent(client=self._client(self.settings.cost_model), name="cost_security", instructions=ROLE_PROMPTS["cost"]),
        ]
        workflow = ConcurrentBuilder(participants=participants).build()
        events = await workflow.run(task + gate)
        specialist_reports: list[str] = []
        for output in events.get_outputs():
            if not isinstance(output, AgentResponse):
                continue
            for message in output.messages:
                specialist_reports.append(f"[{message.author_name or 'agent'}]\n{message.text}")

        supervisor = Agent(
            client=self._client(self.settings.supervisor_model),
            name="supervisor",
            instructions=(
                "You are Miniverse CEO/Supervisor. Reconcile specialist evidence into one execution decision. "
                "Do not invent evidence. State verified, unverified and broken facts, safest action, tests, rollback, "
                "and whether owner approval is required."
            ),
        )
        result = await supervisor.run(
            f"TASK:\n{task}\n\nSPECIALIST REPORTS:\n" + "\n\n".join(specialist_reports) + gate
        )
        return result.text
