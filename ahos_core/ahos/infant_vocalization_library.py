from __future__ import annotations

import hashlib
import json
import os
import shutil
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .runpod_ltx2 import PaidExecutionApproval
from .runpod_qwen3_voice_design import (
    RunPodQwen3VoiceDesignConfig,
    RunPodQwen3VoiceDesignProvider,
)


class InfantVocalizationError(RuntimeError):
    pass


VALID_CUES = frozenset({"coo", "tiny_laugh", "soft_fuss", "gentle_cry", "sleepy_breath"})
INFANT_SPECS = {
    "medine": {
        "age_months": 2,
        "direction": "fictional two-month-old baby girl",
    },
    "ramin": {
        "age_months": 1,
        "direction": "fictional one-month-old newborn boy",
    },
}
_CUE_DIRECTIONS = {
    "coo": "calm soft cooing, content and curious",
    "tiny_laugh": "one tiny natural baby chuckle, happy but not theatrical",
    "soft_fuss": "brief soft fussing, mildly uneasy, not crying hard",
    "gentle_cry": "brief gentle infant cry, emotionally safe and not distressed",
    "sleepy_breath": "sleepy breathy murmurs and a tiny yawn",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class InfantVocalization:
    character_id: str
    cue: str
    path: Path
    sha256: str


class InfantVocalizationLibrary:
    """Hash-locked non-verbal infant assets; never falls back to sentence TTS."""

    def __init__(self, studio_root: str | Path) -> None:
        self.root = Path(studio_root).resolve()
        self.manifest_path = self.root / "artifacts" / "infant-vocalizations.json"

    def load(self) -> dict[str, object]:
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InfantVocalizationError(f"cannot read infant library: {exc}") from exc
        if not isinstance(value, dict) or value.get("schema") != "ahos.infant-vocalization-library.v1":
            raise InfantVocalizationError("invalid infant vocalization manifest")
        return value

    def select(self, character_id: str, cue: str) -> InfantVocalization:
        character_id, cue = character_id.strip(), cue.strip().lower()
        if cue not in VALID_CUES:
            raise InfantVocalizationError(f"unsupported infant cue: {cue}")
        manifest = self.load()
        characters = manifest.get("characters")
        if not isinstance(characters, Mapping):
            raise InfantVocalizationError("infant manifest has no characters map")
        character = characters.get(character_id)
        if not isinstance(character, Mapping):
            raise InfantVocalizationError(f"infant library missing: {character_id}")
        assets = character.get("assets")
        if not isinstance(assets, Mapping) or not isinstance(assets.get(cue), Mapping):
            raise InfantVocalizationError(f"infant cue missing: {character_id}/{cue}")
        record = assets[cue]
        relative = str(record.get("path") or "")
        expected = str(record.get("sha256") or "").lower()
        path = (self.root / relative).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise InfantVocalizationError("infant asset escapes studio directory") from exc
        if not path.is_file() or _sha(path) != expected:
            raise InfantVocalizationError(f"infant asset missing or changed: {character_id}/{cue}")
        data = path.read_bytes()
        if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
            raise InfantVocalizationError(f"infant asset is not WAV: {character_id}/{cue}")
        return InfantVocalization(character_id, cue, path, expected)

    def materialize(self, character_id: str, cue: str, target: str | Path) -> InfantVocalization:
        selected = self.select(character_id, cue)
        destination = Path(target)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(selected.path, destination)
        if _sha(destination) != selected.sha256:
            raise InfantVocalizationError("materialized infant asset failed hash verification")
        return selected


class InfantVocalizationFactory:
    """Resumably creates a distinct, non-lexical library for the canonical infants."""

    def __init__(self, studio_root: str | Path) -> None:
        self.root = Path(studio_root).resolve()
        self.manifest_path = self.root / "artifacts" / "infant-vocalizations.json"

    def generate(self, provider: RunPodQwen3VoiceDesignProvider) -> dict[str, object]:
        approval = PaidExecutionApproval(True, True, True)
        manifest: dict[str, object] = {
            "schema": "ahos.infant-vocalization-library.v1",
            "sentence_tts_allowed": False,
            "characters": {},
        }
        if self.manifest_path.exists():
            try:
                existing = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise InfantVocalizationError(f"cannot resume infant library: {exc}") from exc
            if isinstance(existing, dict) and existing.get("schema") == manifest["schema"]:
                manifest = existing
        characters = manifest.setdefault("characters", {})
        if not isinstance(characters, dict):
            raise InfantVocalizationError("infant library characters must be an object")
        for character_id, spec in INFANT_SPECS.items():
            character = characters.setdefault(character_id, {
                "age_months": spec["age_months"], "assets": {}
            })
            if not isinstance(character, dict) or not isinstance(character.get("assets"), dict):
                raise InfantVocalizationError(f"invalid infant record: {character_id}")
            assets = character["assets"]
            for index, cue in enumerate(sorted(VALID_CUES)):
                current = assets.get(cue)
                if isinstance(current, Mapping):
                    path = (self.root / str(current.get("path") or "")).resolve()
                    if path.is_file() and _sha(path) == current.get("sha256"):
                        continue
                audio = provider.design(
                    text="Mm... ah... ooh...",
                    language="English",
                    instruct=(
                        f"Generate only non-lexical infant vocalization: {spec['direction']}; "
                        f"{_CUE_DIRECTIONS[cue]}. No words, no syllabic speech, no adult voice, "
                        "no music, no background sound. Entirely synthetic studio-owned sound."
                    ),
                    candidate_id=f"{character_id}-infant-{cue}-v1",
                    seed=71_003 + int(spec["age_months"]) * 1_000 + index * 97,
                    approval=approval,
                    max_new_tokens=512,
                )
                target = self.root / "runtime-artifacts" / "infants" / character_id / f"{cue}.wav"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(audio)
                assets[cue] = {
                    "path": target.relative_to(self.root).as_posix(),
                    "sha256": _sha(target),
                    "synthetic": True,
                    "non_lexical": True,
                    "generator": provider.provider_id,
                }
                self._write(manifest)
        manifest["complete"] = all(
            isinstance(characters.get(item), Mapping)
            and set(characters[item].get("assets", {})) == set(VALID_CUES)
            for item in INFANT_SPECS
        )
        self._write(manifest)
        return manifest

    def _write(self, manifest: Mapping[str, object]) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.manifest_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.manifest_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio-dir", required=True)
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("command", choices=("generate", "status"))
    args = parser.parse_args()
    factory = InfantVocalizationFactory(args.studio_dir)
    if args.command == "status":
        result = InfantVocalizationLibrary(args.studio_dir).load()
    else:
        if not args.allow_paid:
            raise SystemExit("--allow-paid is required")
        endpoint = os.getenv("RUNPOD_QWEN3_VOICE_DESIGN_ENDPOINT_ID", "").strip()
        if not endpoint:
            raise SystemExit("RUNPOD_QWEN3_VOICE_DESIGN_ENDPOINT_ID is not configured")
        provider = RunPodQwen3VoiceDesignProvider(RunPodQwen3VoiceDesignConfig(endpoint))
        result = factory.generate(provider)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


__all__ = [
    "INFANT_SPECS", "InfantVocalization", "InfantVocalizationError",
    "InfantVocalizationFactory", "InfantVocalizationLibrary", "VALID_CUES",
]


if __name__ == "__main__":
    raise SystemExit(main())
