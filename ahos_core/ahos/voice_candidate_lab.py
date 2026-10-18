from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import struct
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .runpod_ltx2 import PaidExecutionApproval
from .runpod_qwen3_voice_design import (
    RunPodQwen3VoiceDesignConfig,
    RunPodQwen3VoiceDesignProvider,
)


class VoiceCandidateLabError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VoiceCandidateLabError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VoiceCandidateLabError(f"{path} must contain a JSON object")
    return value


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class VoiceCandidateLab:
    """Generate synthetic cast candidates without silently enrolling a voice."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.manifest_path = self.root / "VOICE-CANDIDATES.json"
        self.approvals_path = self.root / "OWNER-VOICE-APPROVALS.json"

    def prepare(self, production_plan: str | Path, *, candidates_per_character: int = 3) -> dict[str, object]:
        if candidates_per_character not in {2, 3}:
            raise ValueError("candidates_per_character must be 2 or 3")
        plan = _read(Path(production_plan))
        raw_characters = plan.get("characters")
        if not isinstance(raw_characters, list) or not raw_characters:
            raise VoiceCandidateLabError("production plan has no characters")

        characters: list[dict[str, object]] = []
        for raw in raw_characters:
            if not isinstance(raw, Mapping):
                raise VoiceCandidateLabError("character plan must be an object")
            character_id = str(raw.get("id") or "").strip()
            mode = str(raw.get("speech_mode") or "").strip()
            if not character_id or not mode:
                raise VoiceCandidateLabError("character id and speech_mode are required")
            if mode == "infant_vocalization":
                characters.append({
                    "character_id": character_id,
                    "display_name": raw.get("name"),
                    "speech_mode": mode,
                    "status": "vocalization_library_required",
                    "candidates": [],
                })
                continue
            seed = int(raw.get("seed") or 0)
            candidates = [
                {
                    "candidate_id": f"{character_id}-{chr(65 + index)}",
                    "seed": seed + index * 7919,
                    "status": "planned",
                    "audio_path": None,
                    "sha256": None,
                }
                for index in range(candidates_per_character)
            ]
            characters.append({
                "character_id": character_id,
                "display_name": raw.get("name"),
                "age_years": raw.get("age_years"),
                "gender": raw.get("gender"),
                "speech_mode": mode,
                "direction": raw.get("direction"),
                "design_text": raw.get("en_text"),
                "production_text": raw.get("tr_text"),
                "status": "awaiting_generation",
                "candidates": candidates,
            })
        manifest: dict[str, object] = {
            "schema": "ahos.voice-candidate-manifest.v1",
            "created_at": _now(),
            "design_provider": "qwen3-tts-voice-design",
            "design_language": "English",
            "canonical_binding_created": False,
            "characters": characters,
        }
        _write(self.manifest_path, manifest)
        return manifest

    def generate(self, character_id: str, provider: RunPodQwen3VoiceDesignProvider) -> dict[str, object]:
        manifest = _read(self.manifest_path)
        characters = manifest.get("characters")
        if not isinstance(characters, list):
            raise VoiceCandidateLabError("candidate manifest is invalid")
        character = next(
            (item for item in characters if isinstance(item, dict) and item.get("character_id") == character_id),
            None,
        )
        if character is None:
            raise VoiceCandidateLabError(f"unknown character: {character_id}")
        if character.get("speech_mode") == "infant_vocalization":
            raise VoiceCandidateLabError("infants require a vocalization library, not sentence TTS")
        candidates = character.get("candidates")
        if not isinstance(candidates, list):
            raise VoiceCandidateLabError("character candidates are invalid")
        text, direction = str(character.get("design_text") or ""), str(character.get("direction") or "")
        approval = PaidExecutionApproval(True, True, True)
        output = self.root / "audio" / character_id
        output.mkdir(parents=True, exist_ok=True)
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise VoiceCandidateLabError("candidate must be an object")
            if candidate.get("status") == "generated":
                continue
            candidate_id = str(candidate["candidate_id"])
            audio = provider.design(
                text=text,
                language="English",
                instruct=(
                    "Create an entirely fictional studio-owned voice with no resemblance "
                    "to a real person. " + direction
                ),
                candidate_id=candidate_id,
                seed=int(candidate["seed"]),
                approval=approval,
            )
            target = output / f"{candidate_id}.wav"
            target.write_bytes(audio)
            candidate.update({
                "status": "generated",
                "audio_path": target.relative_to(self.root).as_posix(),
                "sha256": _sha256(target),
                "generated_at": _now(),
            })
            _write(self.manifest_path, manifest)
        character["status"] = "awaiting_owner_approval"
        _write(self.manifest_path, manifest)
        return character

    def approve(self, character_id: str, candidate_id: str) -> dict[str, object]:
        return self._approve(character_id, candidate_id, selection=None)

    def _approve(
        self,
        character_id: str,
        candidate_id: str,
        *,
        selection: dict[str, object] | None,
    ) -> dict[str, object]:
        manifest = _read(self.manifest_path)
        characters = manifest.get("characters")
        if not isinstance(characters, list):
            raise VoiceCandidateLabError("candidate manifest is invalid")
        character = next(
            (item for item in characters if isinstance(item, dict) and item.get("character_id") == character_id),
            None,
        )
        if character is None:
            raise VoiceCandidateLabError(f"unknown character: {character_id}")
        candidates = character.get("candidates")
        if not isinstance(candidates, list):
            raise VoiceCandidateLabError("character candidates are invalid")
        candidate = next(
            (item for item in candidates if isinstance(item, dict) and item.get("candidate_id") == candidate_id),
            None,
        )
        if candidate is None or candidate.get("status") != "generated":
            raise VoiceCandidateLabError("only a generated candidate can be approved")
        audio = self.root / str(candidate.get("audio_path") or "")
        if not audio.is_file() or _sha256(audio) != candidate.get("sha256"):
            raise VoiceCandidateLabError("candidate audio is missing or changed")

        approvals = _read(self.approvals_path) if self.approvals_path.exists() else {
            "schema": "ahos.owner-voice-approvals.v1", "approvals": {}
        }
        items = approvals.get("approvals")
        if not isinstance(items, dict):
            raise VoiceCandidateLabError("approval ledger is invalid")
        if character_id in items:
            raise VoiceCandidateLabError(
                f"{character_id} already has an approved voice; explicit versioned override is required"
            )
        record = {
            "character_id": character_id,
            "candidate_id": candidate_id,
            "audio_path": candidate["audio_path"],
            "sha256": candidate["sha256"],
            "reference_origin": "synthetic",
            "rights_confirmed": True,
            "human_character_fit_approved": selection is None,
            "owner_approved": True,
            "owner_selection_delegated": selection is not None,
            "selection": selection,
            "approved_at": _now(),
            "canonical_binding_created": False,
        }
        items[character_id] = record
        character["status"] = "owner_approved"
        character["approved_candidate_id"] = candidate_id
        _write(self.approvals_path, approvals)
        _write(self.manifest_path, manifest)
        return record

    @staticmethod
    def _technical_audio_score(path: Path) -> dict[str, object]:
        """Score objective WAV health without pretending to judge human taste."""
        try:
            with wave.open(str(path), "rb") as wav:
                channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                sample_rate = wav.getframerate()
                frame_count = wav.getnframes()
                raw = wav.readframes(frame_count)
        except (OSError, EOFError, wave.Error) as exc:
            raise VoiceCandidateLabError(f"invalid WAV {path}: {exc}") from exc
        if channels not in {1, 2} or sample_width != 2 or sample_rate < 16_000 or frame_count <= 0:
            raise VoiceCandidateLabError(f"unsupported WAV format: {path}")
        samples = struct.unpack(f"<{len(raw) // 2}h", raw)
        if not samples:
            raise VoiceCandidateLabError(f"empty WAV: {path}")
        duration = frame_count / sample_rate
        peak = max(abs(value) for value in samples) / 32768.0
        rms = math.sqrt(sum(value * value for value in samples) / len(samples)) / 32768.0
        clipping = sum(abs(value) >= 32700 for value in samples) / len(samples)
        silence = sum(abs(value) < 180 for value in samples) / len(samples)
        if duration < 0.35 or duration > 30 or rms < 0.004:
            raise VoiceCandidateLabError(f"unusable WAV signal: {path}")
        score = 100.0
        score -= clipping * 800.0
        score -= max(0.0, silence - 0.28) * 45.0
        score -= abs(peak - 0.88) * 12.0
        score -= abs(rms - 0.16) * 20.0
        return {
            "score": round(max(0.0, score), 4),
            "duration_seconds": round(duration, 4),
            "sample_rate_hz": sample_rate,
            "channels": channels,
            "peak": round(peak, 6),
            "rms": round(rms, 6),
            "clipping_ratio": round(clipping, 8),
            "silence_ratio": round(silence, 6),
        }

    def auto_select(self, character_id: str) -> dict[str, object]:
        manifest = _read(self.manifest_path)
        characters = manifest.get("characters")
        if not isinstance(characters, list):
            raise VoiceCandidateLabError("candidate manifest is invalid")
        character = next(
            (item for item in characters if isinstance(item, dict) and item.get("character_id") == character_id),
            None,
        )
        if character is None:
            raise VoiceCandidateLabError(f"unknown character: {character_id}")
        candidates = character.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise VoiceCandidateLabError("character has no speech candidates")
        ranked: list[tuple[float, str, dict[str, object]]] = []
        for candidate in candidates:
            if not isinstance(candidate, dict) or candidate.get("status") != "generated":
                raise VoiceCandidateLabError("all candidates must be generated before automatic selection")
            candidate_id = str(candidate["candidate_id"])
            audio = self.root / str(candidate.get("audio_path") or "")
            if not audio.is_file() or _sha256(audio) != candidate.get("sha256"):
                raise VoiceCandidateLabError("candidate audio is missing or changed")
            metrics = self._technical_audio_score(audio)
            candidate["technical_qa"] = metrics
            ranked.append((float(metrics["score"]), candidate_id, metrics))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        selected_score, selected_id, _ = ranked[0]
        _write(self.manifest_path, manifest)
        selection = {
            "method": "delegated_owner_policy_v1",
            "technical_qa_passed": True,
            "age_years": character.get("age_years"),
            "gender": character.get("gender"),
            "speech_mode": character.get("speech_mode"),
            "direction": character.get("direction"),
            "selected_score": selected_score,
            "ranking": [
                {"candidate_id": candidate_id, "score": score}
                for score, candidate_id, _metrics in ranked
            ],
        }
        return self._approve(character_id, selected_id, selection=selection)

    def auto_cast(self, provider: RunPodQwen3VoiceDesignProvider) -> dict[str, object]:
        manifest = _read(self.manifest_path)
        characters = manifest.get("characters")
        if not isinstance(characters, list):
            raise VoiceCandidateLabError("candidate manifest is invalid")
        selected: list[dict[str, object]] = []
        infants: list[str] = []
        for character in characters:
            if not isinstance(character, dict):
                continue
            character_id = str(character.get("character_id") or "")
            if character.get("speech_mode") == "infant_vocalization":
                infants.append(character_id)
                continue
            approvals = _read(self.approvals_path).get("approvals", {}) if self.approvals_path.exists() else {}
            if isinstance(approvals, dict) and character_id in approvals:
                selected.append(approvals[character_id])
                continue
            self.generate(character_id, provider)
            selected.append(self.auto_select(character_id))
        report = {
            "schema": "ahos.automatic-voice-casting-report.v1",
            "completed_at": _now(),
            "selected_voices": selected,
            "infant_vocalization_library_required": infants,
            "canonical_binding_created": False,
        }
        _write(self.root / "AUTOMATIC-CASTING-REPORT.json", report)
        return report

    def status(self) -> dict[str, object]:
        manifest = _read(self.manifest_path)
        characters = manifest.get("characters", [])
        counts: dict[str, int] = {}
        if isinstance(characters, list):
            for item in characters:
                if isinstance(item, Mapping):
                    status = str(item.get("status") or "unknown")
                    counts[status] = counts.get(status, 0) + 1
        return {"manifest": str(self.manifest_path), "counts": counts, "characters": characters}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--plan", default="config/core-cast-voice-production-plan.json")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--candidates", type=int, default=3)
    generate = sub.add_parser("generate")
    generate.add_argument("--character", required=True)
    generate.add_argument("--allow-paid", action="store_true")
    approve = sub.add_parser("approve")
    approve.add_argument("--character", required=True)
    approve.add_argument("--candidate", required=True)
    auto_select = sub.add_parser("auto-select")
    auto_select.add_argument("--character", required=True)
    auto_cast = sub.add_parser("auto-cast")
    auto_cast.add_argument("--allow-paid", action="store_true")
    auto_cast.add_argument("--owner-delegated-selection", action="store_true")
    sub.add_parser("status")
    args = parser.parse_args()

    lab = VoiceCandidateLab(args.root)
    if args.command == "prepare":
        result = lab.prepare(args.plan, candidates_per_character=args.candidates)
    elif args.command == "generate":
        if not args.allow_paid:
            raise SystemExit("--allow-paid is required for RunPod voice generation")
        endpoint = os.getenv("RUNPOD_QWEN3_VOICE_DESIGN_ENDPOINT_ID", "").strip()
        if not endpoint:
            raise SystemExit("RUNPOD_QWEN3_VOICE_DESIGN_ENDPOINT_ID is not configured")
        provider = RunPodQwen3VoiceDesignProvider(RunPodQwen3VoiceDesignConfig(endpoint))
        result = lab.generate(args.character, provider)
    elif args.command == "approve":
        result = lab.approve(args.character, args.candidate)
    elif args.command == "auto-select":
        result = lab.auto_select(args.character)
    elif args.command == "auto-cast":
        if not args.allow_paid or not args.owner_delegated_selection:
            raise SystemExit("--allow-paid and --owner-delegated-selection are required")
        endpoint = os.getenv("RUNPOD_QWEN3_VOICE_DESIGN_ENDPOINT_ID", "").strip()
        if not endpoint:
            raise SystemExit("RUNPOD_QWEN3_VOICE_DESIGN_ENDPOINT_ID is not configured")
        provider = RunPodQwen3VoiceDesignProvider(RunPodQwen3VoiceDesignConfig(endpoint))
        result = lab.auto_cast(provider)
    else:
        result = lab.status()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
