from __future__ import annotations

from dataclasses import asdict, dataclass

from .core_cast_voice_catalog import CoreCastVoiceSpec, core_voice_spec


class AgeVoicePolicyError(ValueError):
    """Raised when dialogue violates the character's locked age policy."""


@dataclass(frozen=True, slots=True)
class AgeVoicePolicy:
    character_id: str
    age_stage: str
    speech_mode: str
    sentence_tts_allowed: bool
    maximum_words_per_utterance: int | None
    synthetic_reference_required: bool
    exaggeration: float
    cfg_weight: float
    temperature: float
    direction: str

    def to_payload(self) -> dict[str, object]:
        return asdict(self)

    def validate_text(self, text: str) -> None:
        words = tuple(part for part in text.strip().split() if part)
        if not words:
            raise AgeVoicePolicyError(f"{self.character_id}: dialogue text is empty")
        if not self.sentence_tts_allowed:
            raise AgeVoicePolicyError(
                f"{self.character_id}: infant characters use approved vocalization assets, "
                "not sentence TTS"
            )
        if self.maximum_words_per_utterance is not None and len(words) > self.maximum_words_per_utterance:
            raise AgeVoicePolicyError(
                f"{self.character_id}: {self.speech_mode} dialogue has {len(words)} words; "
                f"maximum is {self.maximum_words_per_utterance}"
            )


def policy_for_spec(spec: CoreCastVoiceSpec) -> AgeVoicePolicy:
    if spec.speech_mode == "infant_vocalization":
        return AgeVoicePolicy(spec.character_id, spec.age_stage, spec.speech_mode,
                              False, 0, True, 0.35, 0.65, 0.65,
                              spec.voice_direction)
    if spec.speech_mode == "early_speech":
        return AgeVoicePolicy(spec.character_id, spec.age_stage, spec.speech_mode,
                              True, 8, True, 0.45, 0.60, 0.72,
                              spec.voice_direction)
    if spec.age_stage in {"preschool", "child", "school-age"}:
        return AgeVoicePolicy(spec.character_id, spec.age_stage, spec.speech_mode,
                              True, 18, True, 0.55, 0.55, 0.76,
                              spec.voice_direction)
    return AgeVoicePolicy(spec.character_id, spec.age_stage, spec.speech_mode,
                          True, None, True, 0.45, 0.50, 0.72,
                          spec.voice_direction)


def core_age_voice_policy(character_id: str) -> AgeVoicePolicy:
    return policy_for_spec(core_voice_spec(character_id))


__all__ = ["AgeVoicePolicy", "AgeVoicePolicyError", "core_age_voice_policy", "policy_for_spec"]
