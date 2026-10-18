from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ProductE2EReport:
    accepted: bool
    blockers: tuple[str, ...]


class AndroidProofContract:
    REQUIRED = frozenset({
        "apk_sha256",
        "device_model",
        "android_version",
        "install_passed",
        "launch_passed",
        "smoke_passed",
        "captured_at",
    })

    def evaluate(self, payload: Mapping[str, object]) -> ProductE2EReport:
        blockers = [f"missing:{k}" for k in sorted(self.REQUIRED - set(payload))]
        digest = str(payload.get("apk_sha256") or "")
        if digest and len(digest) != 64:
            blockers.append("invalid_apk_sha256")
        for key in ("install_passed", "launch_passed", "smoke_passed"):
            if key in payload and payload.get(key) is not True:
                blockers.append(f"{key}:false")
        return ProductE2EReport(not blockers, tuple(blockers))


class BrowserProofContract:
    REQUIRED = frozenset({
        "commit_sha",
        "browser",
        "browser_version",
        "base_url",
        "navigation_passed",
        "critical_flow_passed",
        "console_errors",
        "captured_at",
    })

    def evaluate(self, payload: Mapping[str, object]) -> ProductE2EReport:
        blockers = [f"missing:{k}" for k in sorted(self.REQUIRED - set(payload))]
        if payload.get("navigation_passed") is not True:
            blockers.append("navigation_failed")
        if payload.get("critical_flow_passed") is not True:
            blockers.append("critical_flow_failed")
        errors = payload.get("console_errors")
        if isinstance(errors, list) and errors:
            blockers.append("browser_console_errors")
        return ProductE2EReport(not blockers, tuple(blockers))
