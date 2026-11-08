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
                "Existing RunPod deployment is live-verified and suitable as a "
                "lightweight English baseline TTS provider."
            ),
            source_url="https://github.com/hexgrad/kokoro",
        ),
        TechnologyEntry(
            technology_id="qwen3-tts-voice-design",
            name="Qwen3-TTS VoiceDesign 1.7B",
            category="fictional-voice-design",
            status=RadarStatus.TRIAL,
            license_note="Apache-2.0 project; generated voice use still requires normal production-rights review.",
            commercial_default=True,
            rationale=(
                "Natural-language voice design is better suited to creating age-appropriate "
                "fictional character voices than reusing adult stock timbres. Official "
                "VoiceDesign supports English/German/French/Spanish and other listed languages "
                "but not Turkish, so use it to create a synthetic child-like reference and "
                "then route Turkish through the already-verified Chatterbox V3 cross-language "
                "cloning path. Keep in trial until our own child-voice QA passes."
            ),
            source_url="https://github.com/QwenLM/Qwen3-TTS",
        ),
        TechnologyEntry(
            technology_id="chatterbox-multilingual",
            name="Chatterbox Multilingual V3",
            category="tts-voice-cloning",
            status=RadarStatus.TRIAL,
            license_note=(
                "MIT project; generated/reference voice rights remain the studio's "
                "responsibility and must be tracked separately."
            ),
            commercial_default=True,
            rationale=(
                "Latest general-purpose Chatterbox multilingual model. Official upstream "
                "documents 23 supported languages including Turkish, German, Arabic, "
                "French, Spanish and English, with improved speaker similarity, reduced "
                "hallucinations, cross-language voice cloning, and built-in PerTh audio "
                "watermarking. Keep in trial until our own language/character QA passes."
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