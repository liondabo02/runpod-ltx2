from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .audio_pipeline import DEFAULT_LANGUAGE_POLICIES
from .core_cast_voice_catalog import CORE_CAST_VOICE_SPECS, CoreCastVoiceSpec
from .voice_enrollment import VoiceEnrollmentStore


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class VoiceReadinessCell:
    character_id: str
    language: str
    speech_mode: str
    required: bool
    enrolled: bool
    enrollment_version: int | None
    reference_sha256: str | None
    reason: str

    @property
    def ready(self) -> bool:
        return not self.required or self.enrolled


@dataclass(frozen=True, slots=True)
class VoiceReadinessReport:
    required_languages: tuple[str, ...]
    cells: tuple[VoiceReadinessCell, ...]
    report_hash: str

    @property
    def ready(self) -> bool:
        return bool(self.cells) and all(cell.ready for cell in self.cells)

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(
            f"{cell.character_id}:{cell.language}"
            for cell in self.cells
            if cell.required and not cell.enrolled
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "ahos.voice-readiness.v1",
            "required_languages": list(self.required_languages),
            "ready": self.ready,
            "missing": list(self.missing),
            "report_hash": self.report_hash,
            "cells": [
                {
                    "character_id": cell.character_id,
                    "language": cell.language,
                    "speech_mode": cell.speech_mode,
                    "required": cell.required,
                    "enrolled": cell.enrolled,
                    "enrollment_version": cell.enrollment_version,
                    "reference_sha256": cell.reference_sha256,
                    "reason": cell.reason,
                }
                for cell in self.cells
            ],
        }


class CoreCastVoiceReadinessAuditor:
    """Audits canonical enrollment coverage; never creates or approves voices."""

    NON_TTS_MODES = frozenset({"infant_vocalization", "animal_vocalization"})

    def __init__(self, enrollment_store: VoiceEnrollmentStore) -> None:
        self.enrollment_store = enrollment_store

    def audit(
        self,
        *,
        cast: Sequence[CoreCastVoiceSpec] = CORE_CAST_VOICE_SPECS,
        required_languages: Sequence[str] | None = None,
    ) -> VoiceReadinessReport:
        languages = tuple(
            required_languages
            if required_languages is not None
            else (policy.code for policy in DEFAULT_LANGUAGE_POLICIES if policy.required)
        )
        if not languages or len(set(languages)) != len(languages):
            raise ValueError("required languages must be unique and non-empty")
        if not cast or len({spec.character_id for spec in cast}) != len(cast):
            raise ValueError("cast character ids must be unique and non-empty")

        cells: list[VoiceReadinessCell] = []
        for spec in sorted(cast, key=lambda item: item.character_id):
            required = spec.speech_mode not in self.NON_TTS_MODES
            for language in languages:
                enrollment = self.enrollment_store.get(spec.character_id, language) if required else None
                cells.append(
                    VoiceReadinessCell(
                        character_id=spec.character_id,
                        language=language,
                        speech_mode=spec.speech_mode,
                        required=required,
                        enrolled=enrollment is not None,
                        enrollment_version=enrollment.version if enrollment else None,
                        reference_sha256=enrollment.reference_sha256 if enrollment else None,
                        reason=(
                            "canonical enrollment present"
                            if enrollment else
                            "non-TTS vocalization; canonical speech enrollment not required"
                            if not required else
                            "canonical enrollment missing"
                        ),
                    )
                )

        semantic = [
            {
                "character": cell.character_id, "language": cell.language,
                "mode": cell.speech_mode, "required": cell.required,
                "enrolled": cell.enrolled, "version": cell.enrollment_version,
                "sha256": cell.reference_sha256,
            }
            for cell in cells
        ]
        return VoiceReadinessReport(languages, tuple(cells), _digest(semantic))


def export_voice_readiness(report: VoiceReadinessReport, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report.to_payload(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output
