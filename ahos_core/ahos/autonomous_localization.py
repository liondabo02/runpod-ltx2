from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence


class LocalizationPipelineError(RuntimeError):
    """Base error for fail-closed autonomous localization."""


class LocalizationQualityRejected(LocalizationPipelineError):
    pass


@dataclass(frozen=True, slots=True)
class LocalizationIssue:
    code: str
    unit_id: str
    message: str


@dataclass(frozen=True, slots=True)
class LocalizationPolicy:
    maximum_rounds: int = 3
    minimum_length_ratio: float = 0.20
    maximum_length_ratio: float = 4.0

    def __post_init__(self) -> None:
        if self.maximum_rounds < 1:
            raise ValueError("maximum_rounds must be >= 1")
        if not 0 < self.minimum_length_ratio <= 1:
            raise ValueError("minimum_length_ratio must be in (0, 1]")
        if self.maximum_length_ratio < 1:
            raise ValueError("maximum_length_ratio must be >= 1")


class AutonomousLocalizationPipeline:
    """Schema-bound translation and deterministic QA/revision loop.

    The generator is deliberately injected. Production may use an external LLM,
    while tests and rehearsals remain deterministic and network-free.
    """

    _PLACEHOLDERS = ("TODO", "TBD", "TRANSLATE", "[MISSING]", "<TRANSLATION>")

    def __init__(
        self,
        *,
        generator: Callable[[str], str],
        policy: LocalizationPolicy | None = None,
    ) -> None:
        self.generator = generator
        self.policy = policy or LocalizationPolicy()

    def localize(
        self,
        units: Sequence[Mapping[str, object]],
        *,
        languages: Sequence[str],
        character_name_locks: Mapping[str, str],
        terminology_locks: Mapping[str, Mapping[str, str]] | None = None,
    ) -> dict[str, object]:
        language_set = tuple(dict.fromkeys(str(x).strip().lower() for x in languages))
        if len(language_set) != 7 or any(not item for item in language_set):
            raise ValueError("exactly seven unique languages are required")
        normalized = [self._validate_input_unit(unit, language_set) for unit in units]
        terminology = {
            str(language).lower(): {str(k): str(v) for k, v in terms.items()}
            for language, terms in (terminology_locks or {}).items()
        }
        prior: object | None = None
        issues: tuple[LocalizationIssue, ...] = ()
        for round_number in range(1, self.policy.maximum_rounds + 1):
            prompt = self._contract(
                normalized,
                languages=language_set,
                character_name_locks=character_name_locks,
                terminology_locks=terminology,
                round_number=round_number,
                prior=prior,
                issues=issues,
            )
            raw = self.generator(json.dumps(prompt, ensure_ascii=False, indent=2))
            try:
                payload = self._decode(raw)
                translated = self._parse_translations(payload, normalized)
                issues = self._quality_issues(
                    translated,
                    character_name_locks=character_name_locks,
                    terminology_locks=terminology,
                )
                prior = {"translations": translated}
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                prior = self._recover(raw)
                issues = (
                    LocalizationIssue("schema.invalid", "provider_response", str(exc)),
                )
                continue
            if not issues:
                return {
                    "status": "machine_qa_approved",
                    "qa_rounds": round_number,
                    "fail_closed": True,
                    "units": translated,
                    "issues": [],
                }

        detail = "; ".join(
            f"{issue.code}@{issue.unit_id}: {issue.message}" for issue in issues
        )
        raise LocalizationQualityRejected(
            f"localization failed closed after {self.policy.maximum_rounds} rounds: {detail}"
        )

    @staticmethod
    def _validate_input_unit(
        unit: Mapping[str, object], languages: Sequence[str]
    ) -> dict[str, str]:
        required = (
            "unit_id", "scene_id", "line_id", "speaker_character_id",
            "source_language", "target_language", "source_text",
        )
        result = {key: str(unit[key]).strip() for key in required}
        if any(not value for value in result.values()):
            raise ValueError("localization unit fields must not be empty")
        if result["target_language"].lower() not in languages:
            raise ValueError(f"unsupported target language: {result['target_language']}")
        result["source_language"] = result["source_language"].lower()
        result["target_language"] = result["target_language"].lower()
        existing = str(unit.get("localized_text") or "").strip()
        result["localized_text"] = existing
        return result

    @staticmethod
    def _decode(raw: str) -> Mapping[str, object]:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[-1].strip() == "```":
                text = "\n".join(lines[1:-1])
                if text.lstrip().startswith("json"):
                    text = text.lstrip()[4:].lstrip()
        payload = json.loads(text)
        if not isinstance(payload, Mapping):
            raise TypeError("localization response must be a JSON object")
        return payload

    @staticmethod
    def _recover(raw: str) -> object:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"raw_response": str(raw)[:20000]}

    @staticmethod
    def _parse_translations(
        payload: Mapping[str, object], expected: Sequence[Mapping[str, str]]
    ) -> list[dict[str, str]]:
        rows = payload["translations"]
        if not isinstance(rows, list):
            raise TypeError("translations must be an array")
        by_id: dict[str, Mapping[str, object]] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                raise TypeError("each translation must be an object")
            unit_id = str(row["unit_id"]).strip()
            if not unit_id or unit_id in by_id:
                raise ValueError(f"duplicate or empty unit_id: {unit_id!r}")
            by_id[unit_id] = row
        expected_ids = {unit["unit_id"] for unit in expected}
        if set(by_id) != expected_ids:
            missing = sorted(expected_ids - set(by_id))
            extra = sorted(set(by_id) - expected_ids)
            raise ValueError(f"unit coverage mismatch; missing={missing}, extra={extra}")

        output: list[dict[str, str]] = []
        for unit in expected:
            row = by_id[unit["unit_id"]]
            text = str(row["localized_text"]).strip()
            output.append({
                **unit,
                "localized_text": text,
                "status": "machine_qa_approved",
            })
        return output

    def _quality_issues(
        self,
        units: Sequence[Mapping[str, str]],
        *,
        character_name_locks: Mapping[str, str],
        terminology_locks: Mapping[str, Mapping[str, str]],
    ) -> tuple[LocalizationIssue, ...]:
        issues: list[LocalizationIssue] = []
        locked_names = tuple(str(name).strip() for name in character_name_locks.values())
        for unit in units:
            unit_id = unit["unit_id"]
            source = unit["source_text"].strip()
            localized = unit["localized_text"].strip()
            target = unit["target_language"]
            if not localized:
                issues.append(LocalizationIssue("text.empty", unit_id, "localized text is empty"))
                continue
            if any(token.casefold() in localized.casefold() for token in self._PLACEHOLDERS):
                issues.append(LocalizationIssue("text.placeholder", unit_id, "placeholder text remains"))
            if unit["source_language"] == target and localized != source:
                issues.append(LocalizationIssue("source.changed", unit_id, "source-language text must remain exact"))
            if unit["source_language"] != target:
                if localized.casefold() == source.casefold():
                    issues.append(
                        LocalizationIssue(
                            "translation.unchanged",
                            unit_id,
                            "target-language text is unchanged from the source",
                        )
                    )
                source_size = max(1, len(re.findall(r"\w+", source, flags=re.UNICODE)))
                target_size = len(re.findall(r"\w+", localized, flags=re.UNICODE))
                ratio = target_size / source_size
                if ratio < self.policy.minimum_length_ratio or ratio > self.policy.maximum_length_ratio:
                    issues.append(LocalizationIssue("length.ratio", unit_id, f"word ratio {ratio:.2f} is outside policy"))
            for name in locked_names:
                if name and name.casefold() in source.casefold() and name.casefold() not in localized.casefold():
                    issues.append(LocalizationIssue("name.lock", unit_id, f"canonical name {name!r} changed or disappeared"))
            for source_term, approved_term in terminology_locks.get(target, {}).items():
                if source_term.casefold() in source.casefold() and approved_term.casefold() not in localized.casefold():
                    issues.append(LocalizationIssue("terminology.lock", unit_id, f"required term {approved_term!r} is missing"))
        return tuple(issues)

    @staticmethod
    def _contract(
        units: Sequence[Mapping[str, str]],
        *,
        languages: Sequence[str],
        character_name_locks: Mapping[str, str],
        terminology_locks: Mapping[str, Mapping[str, str]],
        round_number: int,
        prior: object | None,
        issues: Sequence[LocalizationIssue],
    ) -> dict[str, object]:
        return {
            "contract": "ahos.autonomous-localization.v1",
            "role": "senior_children_media_localization_team",
            "round": round_number,
            "instructions": [
                "Return JSON only and exactly one translation for every unit_id.",
                "Preserve meaning, emotion, age suitability, speaker intent and natural spoken rhythm.",
                "Never translate, rename or inflect canonical character names.",
                "Obey locked terminology exactly and do not add explanations.",
                "For source_language == target_language copy source_text exactly.",
            ],
            "languages": list(languages),
            "character_name_locks": dict(character_name_locks),
            "terminology_locks": {key: dict(value) for key, value in terminology_locks.items()},
            "required_schema": {
                "translations": [{"unit_id": "exact input id", "localized_text": "non-empty string"}]
            },
            "units": [dict(unit) for unit in units],
            "previous_response": prior,
            "quality_failures": [
                {"code": issue.code, "unit_id": issue.unit_id, "message": issue.message}
                for issue in issues
            ],
        }
