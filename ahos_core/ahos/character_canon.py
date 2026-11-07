"""Tek karakter kanonu — eski Character Bible + ses katalogu + görsel kanon.

Amaç: yeni çizgi film hattı ile eski karakter hafızasını **tek okuma katmanında**
birleştirmek. Bu modül hiçbir şey yazmaz, veritabanı oluşturmaz, ağ çağrısı yapmaz.

Katmanlar:
1. `CharacterBibleStore` (control_plane_v2/.../character-memory.db): kimlik, sürüm,
   aile ilişkileri, kanonik bilgiler.
2. `core_cast_voice_catalog`: cinsiyet, yaş, konuşma biçimi, ses yönü.
3. `characters/*.json`: görsel kanon (bizim üretim dosyaları).
4. `audio/core-voices/<id>/`: mevcut ses varlıkları (silinmez, yalnız denetlenir).

Özel veriler yalnız yerel/private dizinde raporlanır; public repoya yazılmaz.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .character_memory import CharacterBibleStore
from .core_cast_voice_catalog import CORE_CAST_VOICE_SPECS

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_STUDIO = ROOT / "control_plane_v2" / "runtime" / "private" / "animation-studio"
DEFAULT_BIBLE = PRIVATE_STUDIO / "character-memory.db"
DEFAULT_AUDIO = PRIVATE_STUDIO / "audio" / "core-voices"
DEFAULT_VISUALS = ROOT / "characters"

AUDIO_FILES = ("reference-en.wav", "tr.wav")
GENDER_WORDS = {
    "female": ("girl", "woman", "sister", "she ", " her "),
    "male": ("boy", "man ", "brother", "he ", " his "),
}
EXPECTED = {"characters": 16, "relationships": 28, "canon_facts": 3}
BABIES = {"medine", "ramin"}


class CanonError(RuntimeError):
    pass


@dataclass(frozen=True)
class CanonEntry:
    character_id: str
    display_name: str
    role: str
    family_group: str
    age_stage: str
    version: int
    gender: str
    speech_mode: str
    voice_direction: str
    visual_path: str
    audio: dict[str, dict]
    issues: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "character_id": self.character_id, "display_name": self.display_name,
            "role": self.role, "family_group": self.family_group,
            "age_stage": self.age_stage, "version": self.version,
            "gender": self.gender, "speech_mode": self.speech_mode,
            "voice_direction": self.voice_direction, "visual_path": self.visual_path,
            "audio": self.audio, "issues": list(self.issues),
        }


def _normalize_gender(value: str) -> str:
    text = str(value or "").strip().lower()
    if text in {"girl", "woman", "female", "kız", "kadın"}:
        return "female"
    if text in {"boy", "man", "male", "erkek"}:
        return "male"
    return text


def _voice_map() -> dict[str, object]:
    return {spec.character_id: spec for spec in CORE_CAST_VOICE_SPECS}


def _visual_entry(visuals: Path, character_id: str) -> tuple[str, str]:
    path = visuals / f"{character_id}.json"
    if not path.is_file():
        return "", ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return str(path), ""
    return str(path), str(payload.get("prompt_fragment") or "")


def _visual_gender_conflict(prompt: str, gender: str) -> bool:
    if not prompt:
        return False
    lowered = f" {prompt.lower()} "
    expected_words = GENDER_WORDS.get(gender, ())
    other = "male" if gender == "female" else "female"
    opposite_words = GENDER_WORDS.get(other, ())
    # Karşı cins kelimesi var, beklenen kelime yoksa çelişki.
    return any(word in lowered for word in opposite_words) and not any(
        word in lowered for word in expected_words)


class CharacterCanon:
    """Salt okunur birleşik kanon görünümü."""

    def __init__(self, *, bible_path: Path | None = None, visuals: Path | None = None,
                 audio: Path | None = None) -> None:
        self.bible_path = Path(bible_path or DEFAULT_BIBLE)
        self.visuals = Path(visuals or DEFAULT_VISUALS)
        self.audio = Path(audio or DEFAULT_AUDIO)
        self.store = CharacterBibleStore(self.bible_path)
        self._voices = _voice_map()

    # ---------------------------------------------------------------- layers
    def entries(self) -> tuple[CanonEntry, ...]:
        rows: list[CanonEntry] = []
        for character_id in self.store.character_ids():
            profile = self.store.get_profile(character_id)
            if profile is None:  # pragma: no cover - store tutarlılığı
                continue
            spec = self._voices.get(character_id)
            gender = _normalize_gender(getattr(spec, "gender_presentation", ""))
            visual_path, prompt = _visual_entry(self.visuals, character_id)
            audio = {}
            for name in AUDIO_FILES:
                path = self.audio / character_id / name
                audio[name] = {"exists": path.is_file(),
                               "bytes": path.stat().st_size if path.is_file() else 0}
            issues: list[str] = []
            if spec is None:
                issues.append("voice_spec_missing")
            if not gender:
                issues.append("gender_missing")
            if not visual_path:
                issues.append("visual_canon_missing")
            if prompt and gender and _visual_gender_conflict(prompt, gender):
                issues.append("gender_conflict")
            if not audio[AUDIO_FILES[0]]["exists"] or not audio[AUDIO_FILES[1]]["exists"]:
                issues.append("audio_asset_missing")
            rows.append(CanonEntry(
                character_id=character_id, display_name=profile.display_name,
                role=profile.canonical_role, family_group=profile.family_group,
                age_stage=profile.age_stage,
                version=len(self.store.version_history(character_id)),
                gender=gender, speech_mode=str(getattr(spec, "speech_mode", "")),
                voice_direction=str(getattr(spec, "voice_direction", "")),
                visual_path=visual_path, audio=audio, issues=tuple(issues)))
        return tuple(rows)

    def relationships(self) -> tuple[dict, ...]:
        return tuple({"from": rel.from_character_id, "type": rel.relationship_type,
                      "to": rel.to_character_id, "locked": rel.locked}
                     for rel in self.store.relationships())

    def canon_facts(self) -> tuple[dict, ...]:
        return tuple({"key": fact.fact_key, "value": fact.fact_value,
                      "scope": f"{fact.scope_type}:{fact.scope_id}", "locked": fact.locked}
                     for fact in self.store.canon_facts())

    # ------------------------------------------------------------- validation
    def conflicts(self) -> list[dict]:
        """Bulguları ayrı kategorilerde döndürür; teknik kimlik çelişkisi ile
        eksik varlık aynı kovaya konmaz."""

        ids = set(self.store.character_ids())
        problems: list[dict] = []
        for entry in self.entries():
            for issue in entry.issues:
                if issue == "gender_conflict":
                    problems.append({"character_id": entry.character_id, "issue": issue,
                                     "category": "technical_identity_conflict",
                                     "severity": "error"})
                elif issue in {"voice_spec_missing", "gender_missing"}:
                    problems.append({"character_id": entry.character_id, "issue": issue,
                                     "category": "identity_data_missing",
                                     "severity": "error"})
                elif issue in {"missing_visual_canon", "visual_canon_missing"}:
                    problems.append({"character_id": entry.character_id, "issue": issue,
                                     "category": "missing_visual_canon",
                                     "severity": "info"})
                elif issue == "audio_asset_missing":
                    baby = entry.character_id in BABIES
                    problems.append({"character_id": entry.character_id, "issue": issue,
                                     "category": "baby_audio_absent" if baby else "missing_audio_asset",
                                     "severity": "info" if baby else "warning"})
                else:
                    problems.append({"character_id": entry.character_id, "issue": issue,
                                     "category": "other", "severity": "warning"})
        for rel in self.relationships():
            for side in (rel["from"], rel["to"]):
                if side not in ids:
                    problems.append({"character_id": side, "issue": "orphan_relationship",
                                     "category": "technical_identity_conflict",
                                     "severity": "error"})
        return problems

    @staticmethod
    def _by_category(problems: list[dict]) -> dict:
        counts: dict[str, int] = {}
        for item in problems:
            counts[item["category"]] = counts.get(item["category"], 0) + 1
        return dict(sorted(counts.items()))

    def summary(self) -> dict:
        entries = self.entries()
        audio_ok = sum(1 for entry in entries
                       if all(item["exists"] for item in entry.audio.values()))
        problems = self.conflicts()
        return {
            "characters": len(entries),
            "relationships": len(self.relationships()),
            "canon_facts": len(self.canon_facts()),
            "with_visual_canon": sum(1 for entry in entries if entry.visual_path),
            "with_audio_en_tr": audio_ok,
            "gender_known": sum(1 for entry in entries if entry.gender),
            "findings": len(problems),
            "conflicts_by_category": self._by_category(problems),
            "errors": sum(1 for item in problems if item["severity"] == "error"),
            "warnings": sum(1 for item in problems if item["severity"] == "warning"),
            "info": sum(1 for item in problems if item["severity"] == "info"),
            "bible": str(self.bible_path),
            "private": True,
        }

    def assert_consistent(self, expected: dict | None = None) -> dict:
        expected = expected or EXPECTED
        summary = self.summary()
        problems = []
        for key in ("characters", "relationships", "canon_facts"):
            if summary[key] != expected[key]:
                problems.append(f"{key}={summary[key]} (beklenen {expected[key]})")
        errors = [item for item in self.conflicts() if item["severity"] == "error"]
        if errors:
            problems.append(f"{len(errors)} kritik çelişki: " +
                            ", ".join(sorted({item['issue'] for item in errors})))
        if problems:
            raise CanonError("; ".join(problems))
        return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tek karakter kanonu (salt okunur)")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--report", default="")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    canon = CharacterCanon()
    summary = canon.summary()
    if args.check:
        try:
            canon.assert_consistent()
        except CanonError as exc:
            print(json.dumps({"ok": False, "error": str(exc), **summary}, ensure_ascii=False))
            return 1
    if args.report:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema": "ahos.character-canon.v1", "summary": summary,
                   "relationships": list(canon.relationships()),
                   "canon_facts": list(canon.canon_facts()),
                   "characters": [entry.to_dict() for entry in canon.entries()],
                   "conflicts": canon.conflicts()}
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"report": str(target), **summary}, ensure_ascii=False))
        return 0
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
