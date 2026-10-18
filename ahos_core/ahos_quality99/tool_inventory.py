from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class ToolInventoryReport:
    valid: bool
    zero_cost_local_reviewer_available: bool
    deepseek_local_available: bool
    blockers: tuple[str, ...]


class ToolInventoryValidator:
    REQUIRED_TOOLS = ("codex", "claude", "opencode", "ollama", "adb")

    def evaluate(self, payload: Mapping[str, object]) -> ToolInventoryReport:
        blockers: list[str] = []
        tools = payload.get("tools")
        if not isinstance(tools, Mapping):
            return ToolInventoryReport(False, False, False, ("tools_invalid",))

        for name in self.REQUIRED_TOOLS:
            row = tools.get(name)
            if not isinstance(row, Mapping) or row.get("installed") is not True:
                blockers.append(f"tool_missing:{name}")

        models = payload.get("ollama_models")
        if not isinstance(models, Sequence) or isinstance(models, (str, bytes)):
            blockers.append("ollama_models_invalid")
            model_names: set[str] = set()
        else:
            model_names = {str(item) for item in models}

        local_reviewer = any(
            name.startswith(("qwen2.5-coder:", "deepseek-coder:", "deepseek-r1:"))
            for name in model_names
        )
        deepseek_local = any(name.startswith(("deepseek-coder:", "deepseek-r1:")) for name in model_names)
        if not local_reviewer:
            blockers.append("zero_cost_local_coder_model_missing")
        if not deepseek_local:
            blockers.append("deepseek_local_model_missing")

        return ToolInventoryReport(
            valid=not any(item.startswith("tool_missing:") or item == "ollama_models_invalid" for item in blockers),
            zero_cost_local_reviewer_available=local_reviewer,
            deepseek_local_available=deepseek_local,
            blockers=tuple(sorted(set(blockers))),
        )
