from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RadarStatus(str, Enum):
    ADOPT = "adopt"
    TRIAL = "trial"
    ASSESS = "assess"
    HOLD = "hold"


@dataclass(frozen=True, slots=True)
class TechnologyEntry:
    technology_id: str
    name: str
    category: str
    status: RadarStatus
    license_note: str
    commercial_default: bool
    rationale: str
    source_url: str


def studio_technology_radar() -> tuple[TechnologyEntry, ...]:
    return (
        TechnologyEntry(
            technology_id="agent-skills-open-standard",
            name="Agent Skills open standard",
            category="agent-capability-packaging",
            status=RadarStatus.ADOPT,
            license_note="Open standard; individual skills retain their own licenses.",
            commercial_default=True,
            rationale=(
                "Portable SKILL.md packages, progressive disclosure, reusable across "
                "compatible agent clients."
            ),
            source_url="https://agentskills.io/specification",
        ),
        TechnologyEntry(
            technology_id="kokoro-82m",
            name="Kokoro-82M",
            category="tts",
            status=RadarStatus.ADOPT,
            license_note="Apache-2.0 project.",
            commercial_default=True,
            rationale=(
                "Existing RunPod deployment is already available and is suitable as "
                "a lightweight baseline TTS provider where language quality is acceptable."
            ),
            source_url="https://github.com/hexgrad/kokoro",
        ),
        TechnologyEntry(
            technology_id="chatterbox-multilingual",
            name="Chatterbox Multilingual",
            category="tts-voice-cloning",
            status=RadarStatus.TRIAL,
            license_note="MIT project; verify any bundled/reference voice rights separately.",
            commercial_default=True,
            rationale=(
                "Strong candidate for multilingual dubbing and zero-shot voice cloning; "
                "supports Turkish, German, Arabic, French, Spanish and English."
            ),
            source_url="https://github.com/resemble-ai/chatterbox",
        ),
        TechnologyEntry(
            technology_id="fish-speech-s2",
            name="Fish Speech S2",
            category="tts-voice-cloning",
            status=RadarStatus.ASSESS,
            license_note="Fish Audio Research License; commercial suitability must be checked.",
            commercial_default=False,
            rationale=(
                "High-quality multilingual candidate, but licensing makes it unsuitable "
                "as an automatic commercial default without explicit review."
            ),
            source_url="https://github.com/fishaudio/fish-speech",
        ),
        TechnologyEntry(
            technology_id="f5-tts",
            name="F5-TTS",
            category="tts-voice-cloning",
            status=RadarStatus.HOLD,
            license_note=(
                "Code is MIT, but official pretrained weights are CC-BY-NC."
            ),
            commercial_default=False,
            rationale=(
                "Useful research option, but official pretrained weights are not a "
                "default choice for monetized production."
            ),
            source_url="https://github.com/SWivid/F5-TTS",
        ),
        TechnologyEntry(
            technology_id="runpod-serverless",
            name="RunPod Serverless",
            category="remote-compute",
            status=RadarStatus.ADOPT,
            license_note="Hosted compute provider; usage is metered.",
            commercial_default=True,
            rationale=(
                "Existing LTX-2 and Kokoro endpoints fit the laptop-as-control-plane / "
                "remote-GPU-as-factory architecture."
            ),
            source_url="https://docs.runpod.io/",
        ),
    )


def radar_as_dicts() -> list[dict[str, object]]:
    return [
        {
            "technology_id": entry.technology_id,
            "name": entry.name,
            "category": entry.category,
            "status": entry.status.value,
            "license_note": entry.license_note,
            "commercial_default": entry.commercial_default,
            "rationale": entry.rationale,
            "source_url": entry.source_url,
        }
        for entry in studio_technology_radar()
    ]
