from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class IntegrationStatus(str, Enum):
    READY_FOR_SANDBOX = "ready_for_sandbox"
    BLOCKED_PAID = "blocked_paid"
    BLOCKED_COMPUTE = "blocked_compute"
    NEEDS_VERIFICATION = "needs_verification"


class IsolationLevel(str, Enum):
    NONE = "none"
    PROCESS = "process"
    CONTAINER = "container"
    DEDICATED_HOST = "dedicated_host"


@dataclass(frozen=True, slots=True)
class IntegrationCandidate:
    candidate_id: str
    name: str
    kind: str
    source_url: str
    license_name: str
    status: IntegrationStatus
    isolation: IsolationLevel
    capabilities: frozenset[str]
    software_cost_usd: float = 0.0
    hosted_api_free: bool = False
    local_compute_required: bool = False
    credentials_allowed: bool = False
    browser_cookies_allowed: bool = False
    production_allowed: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_id.strip() or not self.name.strip():
            raise ValueError("candidate_id and name must not be empty")
        if not self.capabilities:
            raise ValueError("capabilities must not be empty")
        if self.software_cost_usd < 0:
            raise ValueError("software_cost_usd must be >= 0")


class IntegrationCandidateRegistry:
    """Fail-closed catalog for tools/models that have not entered production."""

    def __init__(self, candidates: Iterable[IntegrationCandidate] = ()) -> None:
        self._candidates: dict[str, IntegrationCandidate] = {}
        for candidate in candidates:
            self.register(candidate)

    def register(self, candidate: IntegrationCandidate) -> None:
        if candidate.candidate_id in self._candidates:
            raise ValueError(f"duplicate candidate_id: {candidate.candidate_id}")
        self._candidates[candidate.candidate_id] = candidate

    def get(self, candidate_id: str) -> IntegrationCandidate | None:
        return self._candidates.get(candidate_id)

    def list(self) -> tuple[IntegrationCandidate, ...]:
        return tuple(sorted(self._candidates.values(), key=lambda c: c.candidate_id))

    def sandbox_eligible(self) -> tuple[IntegrationCandidate, ...]:
        return tuple(
            candidate for candidate in self.list()
            if candidate.status is IntegrationStatus.READY_FOR_SANDBOX
            and candidate.software_cost_usd == 0
            and candidate.isolation in {IsolationLevel.CONTAINER, IsolationLevel.DEDICATED_HOST}
            and not candidate.production_allowed
        )


def default_integration_candidate_registry() -> IntegrationCandidateRegistry:
    return IntegrationCandidateRegistry((
        IntegrationCandidate(
            candidate_id="agent-reach-public", name="Agent Reach (public/read-only profile)",
            kind="research_tool", source_url="https://github.com/Panniantong/Agent-Reach",
            license_name="MIT", status=IntegrationStatus.READY_FOR_SANDBOX,
            isolation=IsolationLevel.CONTAINER,
            capabilities=frozenset({"public_web_research", "rss", "youtube_transcripts", "public_github"}),
            notes="Login, social-cookie extraction, private repositories, write actions and proxies stay disabled.",
        ),
        IntegrationCandidate(
            candidate_id="deer-flow-2", name="DeerFlow 2.0",
            kind="agent_harness", source_url="https://github.com/bytedance/deer-flow",
            license_name="MIT", status=IntegrationStatus.READY_FOR_SANDBOX,
            isolation=IsolationLevel.CONTAINER,
            capabilities=frozenset({"research", "coding", "subagents", "skills", "sandbox"}),
            local_compute_required=True,
            notes="Benchmark only; auto approval, browser control, private-address access and production gateway stay disabled.",
        ),
        IntegrationCandidate(
            candidate_id="remotion-local", name="Remotion (local renderer)",
            kind="video_compositor", source_url="https://github.com/remotion-dev/remotion",
            license_name="Remotion Free License (eligibility limited)",
            status=IntegrationStatus.READY_FOR_SANDBOX,
            isolation=IsolationLevel.CONTAINER,
            capabilities=frozenset({
                "programmatic_video", "episode_assembly", "captions",
                "motion_graphics", "localization_variants", "batch_render",
            }),
            local_compute_required=True,
            notes=(
                "Use only for local evaluation while Free License eligibility applies. "
                "It is a compositor, not a generative video model; rendering consumes local compute. "
                "Recheck licensing before commercial use or organizational growth."
            ),
        ),
        IntegrationCandidate(
            candidate_id="longcat-video", name="Meituan LongCat-Video",
            kind="video_model", source_url="https://github.com/meituan-longcat/LongCat-Video",
            license_name="MIT", status=IntegrationStatus.BLOCKED_COMPUTE,
            isolation=IsolationLevel.DEDICATED_HOST,
            capabilities=frozenset({"text_to_video", "image_to_video", "video_continuation"}),
            local_compute_required=True,
            notes="Code and weights are MIT, but GPU capacity and a zero-cost execution path are not yet verified.",
        ),
        IntegrationCandidate(
            candidate_id="longcat-video-avatar-1.5", name="Meituan LongCat-Video-Avatar 1.5",
            kind="video_model", source_url="https://github.com/meituan-longcat/LongCat-Video",
            license_name="MIT", status=IntegrationStatus.BLOCKED_COMPUTE,
            isolation=IsolationLevel.DEDICATED_HOST,
            capabilities=frozenset({"audio_driven_avatar", "lip_sync", "multi_speaker_video"}),
            local_compute_required=True,
            notes="Strong animation-studio candidate; no run until hardware, weight integrity and zero-cost execution are proven.",
        ),
        IntegrationCandidate(
            candidate_id="longcat-2", name="Meituan LongCat 2.0",
            kind="language_model", source_url="https://huggingface.co/meituan-longcat/LongCat-2.0",
            license_name="unverified", status=IntegrationStatus.NEEDS_VERIFICATION,
            isolation=IsolationLevel.DEDICATED_HOST,
            capabilities=frozenset({"coding", "reasoning", "long_context"}),
            local_compute_required=True,
            notes="Do not route tasks until the exact model card, license and a genuinely free endpoint are verified.",
        ),
        IntegrationCandidate(
            candidate_id="deepseek-v4", name="DeepSeek V4 family",
            kind="language_model", source_url="https://huggingface.co/deepseek-ai",
            license_name="model-specific", status=IntegrationStatus.BLOCKED_COMPUTE,
            isolation=IsolationLevel.DEDICATED_HOST,
            capabilities=frozenset({"coding", "reasoning", "long_context"}),
            local_compute_required=True,
            notes="Open weights do not make hosted inference free. Enable only a currently verified free route or zero-cost local benchmark.",
        ),
        IntegrationCandidate(
            candidate_id="lyria-3.5", name="Google Lyria 3.5",
            kind="music_model", source_url="https://ai.google.dev/gemini-api/docs/music-generation",
            license_name="hosted_service_terms", status=IntegrationStatus.BLOCKED_PAID,
            isolation=IsolationLevel.NONE,
            capabilities=frozenset({"music_generation"}), hosted_api_free=False,
            notes="Consumer app availability is not a free automation API; live routing remains owner-gated and disabled.",
        ),
        IntegrationCandidate(
            candidate_id="ltx-2.5", name="LTX-2.5",
            kind="video_model", source_url="https://huggingface.co/Lightricks/LTX-2.5",
            license_name="LTX-2.x Community License", status=IntegrationStatus.BLOCKED_COMPUTE,
            isolation=IsolationLevel.DEDICATED_HOST,
            capabilities=frozenset({"video_generation", "synchronized_audio", "multi_shot"}),
            local_compute_required=True,
            notes="Weights may be usable under license conditions; hosted API and GPU execution are not free.",
        ),
    ))
