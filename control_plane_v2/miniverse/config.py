from __future__ import annotations

import os
from dataclasses import dataclass


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    supervisor_model: str = os.getenv("MINIVERSE_SUPERVISOR_MODEL", "")
    scout_model: str = os.getenv("MINIVERSE_SCOUT_MODEL", "")
    qa_model: str = os.getenv("MINIVERSE_QA_MODEL", "")
    cost_model: str = os.getenv("MINIVERSE_COST_MODEL", "")
    openhands_model: str = os.getenv("MINIVERSE_OPENHANDS_MODEL", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str | None = os.getenv("MINIVERSE_LLM_BASE_URL") or None
    workspace_root: str = os.getenv("MINIVERSE_WORKSPACE_ROOT", "/workspace")
    max_parallel_agents: int = int(os.getenv("MINIVERSE_MAX_PARALLEL_AGENTS", "4"))
    smoke_mode: bool = _env_flag("MINIVERSE_SMOKE_MODE", False)
    max_budget_per_run_usd: float = float(
        os.getenv("MINIVERSE_MAX_BUDGET_PER_RUN_USD", "0.03")
    )
    queue_db_path: str = os.getenv("MINIVERSE_QUEUE_DB", "/var/lib/miniverse/tasks.db")
    worker_lease_seconds: float = float(os.getenv("MINIVERSE_WORKER_LEASE_SECONDS", "120"))
    worker_heartbeat_seconds: float = float(os.getenv("MINIVERSE_WORKER_HEARTBEAT_SECONDS", "30"))
    worker_retry_base_seconds: float = float(os.getenv("MINIVERSE_WORKER_RETRY_BASE_SECONDS", "15"))
    worker_poll_seconds: float = float(os.getenv("MINIVERSE_WORKER_POLL_SECONDS", "2"))
    worker_health_file: str = os.getenv(
        "MINIVERSE_WORKER_HEALTH_FILE", "/var/lib/miniverse/worker-heartbeat.json"
    )

    def missing_runtime_settings(self) -> list[str]:
        missing: list[str] = []
        required_models = [("MINIVERSE_OPENHANDS_MODEL", self.openhands_model)]
        if not self.smoke_mode:
            required_models = [
                ("MINIVERSE_SUPERVISOR_MODEL", self.supervisor_model),
                ("MINIVERSE_SCOUT_MODEL", self.scout_model),
                ("MINIVERSE_QA_MODEL", self.qa_model),
                ("MINIVERSE_COST_MODEL", self.cost_model),
                ("MINIVERSE_OPENHANDS_MODEL", self.openhands_model),
            ]
        for env_name, value in required_models:
            if not value:
                missing.append(env_name)
        if not (self.openai_api_key or self.llm_api_key):
            missing.append("OPENAI_API_KEY or LLM_API_KEY")
        return missing

