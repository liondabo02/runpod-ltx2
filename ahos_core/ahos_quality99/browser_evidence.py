from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class BrowserEvidenceReport:
    accepted: bool
    blockers: tuple[str, ...]


class ControlCenterBrowserEvidence:
    """Validate captured real-browser evidence without starting a browser."""

    def evaluate(self, payload: Mapping[str, object]) -> BrowserEvidenceReport:
        blockers: list[str] = []
        required = {
            "browser",
            "browser_version",
            "url",
            "http_status",
            "html_length",
            "page_title",
            "screenshot_sha256",
            "screenshot_size_bytes",
            "browser_exit_code",
            "isolated_runtime",
            "server_terminated",
            "captured_at",
        }
        blockers.extend(f"missing:{key}" for key in sorted(required - set(payload)))
        if payload.get("http_status") != 200:
            blockers.append("http_not_200")
        if int(payload.get("html_length") or 0) < 1000:
            blockers.append("html_too_small")
        if payload.get("page_title") != "AHOS Holding Control Center":
            blockers.append("unexpected_page_title")
        digest = str(payload.get("screenshot_sha256") or "")
        if len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
            blockers.append("invalid_screenshot_hash")
        if int(payload.get("screenshot_size_bytes") or 0) < 1000:
            blockers.append("screenshot_too_small")
        if payload.get("browser_exit_code") != 0:
            blockers.append("browser_failed")
        if payload.get("isolated_runtime") is not True:
            blockers.append("runtime_not_isolated")
        if payload.get("server_terminated") is not True:
            blockers.append("server_not_terminated")
        return BrowserEvidenceReport(not blockers, tuple(sorted(set(blockers))))
