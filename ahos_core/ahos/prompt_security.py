from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class PromptSecurityReport:
    safe: bool
    findings: tuple[str, ...]


class PromptSecurityGuard:
    PATTERNS = {
        "authority_override": re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
        "secret_request": re.compile(r"(reveal|print|show).{0,30}(api[_ -]?key|password|token|secret)", re.I),
        "shell_execution": re.compile(r"(run|execute).{0,20}(powershell|cmd\.exe|bash|sh\s+-c)", re.I),
        "approval_bypass": re.compile(r"(bypass|disable|remove).{0,30}(approval|guard|safety|policy)", re.I),
    }

    def inspect(self, text: str) -> PromptSecurityReport:
        findings = tuple(name for name, pattern in self.PATTERNS.items() if pattern.search(text or ""))
        return PromptSecurityReport(not findings, findings)
