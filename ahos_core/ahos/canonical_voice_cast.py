from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .character_memory import CharacterBibleStore
from .voice_continuity import VoiceContinuityStore
from .voice_enrollment import VoiceEnrollment, VoiceEnrollmentStore


DEFAULT_LANGUAGES = ("tr", "de", "ar", "fr", "es", "en")
PROVIDER_ID = "chatterbox-multilingual"


class CanonicalVoiceCastError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalVoiceCastError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CanonicalVoiceCastError(f"{path} must contain a JSON object")
    return value


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_enrollment(
    current: VoiceEnrollment,
    *,
    provider_id: str,
    voice_id: str,
    speaking_style: str,
    reference_audio_uri: str,
    reference_sha256: str,
) -> bool:
    return (
        current.provider_id == provider_id
        and current.voice_id == voice_id
        and current.speaking_style == speaking_style
        and current.reference_audio_uri == reference_audio_uri
        and current.reference_sha256 == reference_sha256
        and current.reference_origin == "synthetic"
        and current.rights_confirmed
        and current.owner_approved
    )


class CanonicalVoiceCastBinder:
    """Hash-lock delegated synthetic voice choices to recurring characters."""

    def __init__(
        self,
        lab_root: str | Path,
        *,
        character_store: CharacterBibleStore,
        voice_store: VoiceContinuityStore,
        enrollment_store: VoiceEnrollmentStore,
    ) -> None:
        self.root = Path(lab_root)
        self.character_store = character_store
        self.voice_store = voice_store
        self.enrollments = enrollment_store
        self.approvals_path = self.root / "OWNER-VOICE-APPROVALS.json"
        self.manifest_path = self.root / "VOICE-CANDIDATES.json"
        self.casting_report_path = self.root / "AUTOMATIC-CASTING-REPORT.json"
        self.report_path = self.root / "CANONICAL-VOICE-BINDING-REPORT.json"

    def bind(
        self,
        *,
        languages: tuple[str, ...] = DEFAULT_LANGUAGES,
        allow_versioned_override: bool = False,
    ) -> dict[str, object]:
        normalized_languages = tuple(dict.fromkeys(item.strip().lower() for item in languages if item.strip()))
        if not normalized_languages:
            raise CanonicalVoiceCastError("at least one language is required")
        unsupported = sorted(set(normalized_languages) - set(DEFAULT_LANGUAGES))
        if unsupported:
            raise CanonicalVoiceCastError(
                "identity-preserving canonical binding is not configured for: "
                + ", ".join(unsupported)
            )

        approvals = _read(self.approvals_path)
        raw_items = approvals.get("approvals")
        if not isinstance(raw_items, Mapping) or not raw_items:
            raise CanonicalVoiceCastError("approval ledger contains no selected voices")

        bound: list[dict[str, object]] = []
        unchanged: list[dict[str, object]] = []
        for key in sorted(raw_items):
            raw = raw_items[key]
            if not isinstance(raw, Mapping):
                raise CanonicalVoiceCastError(f"invalid approval for {key}")
            character_id = str(raw.get("character_id") or key).strip()
            if self.character_store.get_profile(character_id) is None:
                raise CanonicalVoiceCastError(f"unknown character in character bible: {character_id}")
            if not raw.get("owner_approved"):
                raise CanonicalVoiceCastError(f"voice is not owner-approved: {character_id}")
            if raw.get("reference_origin") != "synthetic" or not raw.get("rights_confirmed"):
                raise CanonicalVoiceCastError(f"voice provenance/rights are invalid: {character_id}")
            audio_path = str(raw.get("audio_path") or "").strip()
            expected_sha = str(raw.get("sha256") or "").strip().lower()
            audio = (self.root / audio_path).resolve()
            try:
                audio.relative_to(self.root.resolve())
            except ValueError as exc:
                raise CanonicalVoiceCastError(f"audio path escapes lab root: {character_id}") from exc
            if not audio.is_file() or _sha256(audio) != expected_sha:
                raise CanonicalVoiceCastError(f"approved audio is missing or changed: {character_id}")

            selection = raw.get("selection")
            direction = selection.get("direction") if isinstance(selection, Mapping) else None
            speaking_style = str(direction or "age-appropriate, clear, warm").strip()
            candidate_id = str(raw.get("candidate_id") or "").strip()
            if not candidate_id:
                raise CanonicalVoiceCastError(f"approved candidate id is missing: {character_id}")
            voice_id = f"canonical-{character_id}-{candidate_id}-v1"
            reference_uri = str(audio)

            for language in normalized_languages:
                current = self.enrollments.get(character_id, language)
                if current is not None and _same_enrollment(
                    current,
                    provider_id=PROVIDER_ID,
                    voice_id=voice_id,
                    speaking_style=speaking_style,
                    reference_audio_uri=reference_uri,
                    reference_sha256=expected_sha,
                ):
                    unchanged.append({
                        "character_id": character_id,
                        "language": language,
                        "version": current.version,
                    })
                    continue
                if current is not None and not allow_versioned_override:
                    raise CanonicalVoiceCastError(
                        f"canonical voice already differs for {character_id}/{language}; "
                        "--allow-versioned-override is required"
                    )
                enrollment, binding = self.enrollments.enroll(
                    character_id=character_id,
                    language=language,
                    provider_id=PROVIDER_ID,
                    voice_id=voice_id,
                    speaking_style=speaking_style,
                    reference_audio_uri=reference_uri,
                    reference_sha256=expected_sha,
                    reference_origin="synthetic",
                    rights_confirmed=True,
                    speaker_consent_confirmed=False,
                    human_similarity_approved=False,
                    owner_approved=True,
                )
                bound.append({
                    "character_id": character_id,
                    "language": language,
                    "enrollment_version": enrollment.version,
                    "binding_version": binding.version,
                    "voice_id": voice_id,
                    "reference_sha256": expected_sha,
                })

        infants: list[str] = []
        if self.manifest_path.exists():
            manifest = _read(self.manifest_path)
            characters = manifest.get("characters")
            if isinstance(characters, list):
                infants = sorted(
                    str(item.get("character_id"))
                    for item in characters
                    if isinstance(item, Mapping) and item.get("speech_mode") == "infant_vocalization"
                )
            manifest["canonical_binding_created"] = True
            manifest["canonical_binding_report"] = self.report_path.name
            _write(self.manifest_path, manifest)

        for path in (self.approvals_path, self.casting_report_path):
            if path.exists():
                ledger = _read(path)
                ledger["canonical_binding_created"] = True
                ledger["canonical_binding_report"] = self.report_path.name
                _write(path, ledger)

        report: dict[str, object] = {
            "schema": "ahos.canonical-voice-binding-report.v1",
            "completed_at": _now(),
            "provider_id": PROVIDER_ID,
            "languages_bound": list(normalized_languages),
            "bound": bound,
            "unchanged": unchanged,
            "infant_vocalization_library_required": infants,
            "pending_language_bindings": {
                "ku-latn": "identity-preserving Kurmanji voice transfer is required"
            },
            "canonical_binding_created": True,
        }
        _write(self.report_path, report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lab-root", required=True)
    parser.add_argument("--characters-db", required=True)
    parser.add_argument("--voice-db", required=True)
    parser.add_argument("--enrollment-db", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    bind = sub.add_parser("bind")
    bind.add_argument("--languages", default=",".join(DEFAULT_LANGUAGES))
    bind.add_argument("--allow-versioned-override", action="store_true")
    args = parser.parse_args()

    characters = CharacterBibleStore(args.characters_db)
    voices = VoiceContinuityStore(args.voice_db, character_store=characters)
    enrollments = VoiceEnrollmentStore(
        args.enrollment_db,
        character_store=characters,
        voice_store=voices,
    )
    binder = CanonicalVoiceCastBinder(
        args.lab_root,
        character_store=characters,
        voice_store=voices,
        enrollment_store=enrollments,
    )
    result = binder.bind(
        languages=tuple(args.languages.split(",")),
        allow_versioned_override=args.allow_versioned_override,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
