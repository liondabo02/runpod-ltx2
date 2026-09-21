from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from typing import Iterable


KURMANJI_LANGUAGE = "ku-latn"
KURMANJI_ALPHABET = frozenset("abcçdeêfghîijklmnoöpqrsştuûvwxyz")
REGIONAL_COVERAGE = (
    "Adiyaman-Kahta",
    "Diyarbakir",
    "Sanliurfa",
    "Batman",
    "Mardin",
)


class KurmanjiQualityError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class KurmanjiLineReview:
    line_id: str
    localized_text: str
    native_reviewer: str
    terminology_approved: bool
    pronunciation_approved: bool
    timing_approved: bool
    child_audience_approved: bool


@dataclass(frozen=True, slots=True)
class KurmanjiQualityReport:
    language: str
    register: str
    regions: tuple[str, ...]
    line_count: int
    blocking_issues: tuple[str, ...]
    advisory_issues: tuple[str, ...]
    ready: bool
    report_hash: str

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "ahos.kurmanji-localization-quality.v1",
            "language": self.language,
            "register": self.register,
            "regions": list(self.regions),
            "line_count": self.line_count,
            "blocking_issues": list(self.blocking_issues),
            "advisory_issues": list(self.advisory_issues),
            "ready": self.ready,
            "report_hash": self.report_hash,
        }


class KurmanjiQualityGate:
    """Fail-closed editorial gate for broad Southeast-Turkey Kurmanji releases."""

    register = "neutral-southeast-kurmanji-childrens-animation"

    def evaluate(self, reviews: Iterable[KurmanjiLineReview]) -> KurmanjiQualityReport:
        rows = tuple(reviews)
        if not rows:
            raise KurmanjiQualityError("at least one Kurmanji line review is required")
        ids = [row.line_id.strip() for row in rows]
        if any(not line_id for line_id in ids) or len(ids) != len(set(ids)):
            raise KurmanjiQualityError("line IDs must be non-empty and unique")

        blocking: list[str] = []
        advisory: list[str] = []
        for row in rows:
            text = row.localized_text.strip()
            prefix = f"{row.line_id}:"
            if not text:
                blocking.append(prefix + "missing-text")
                continue
            if text != unicodedata.normalize("NFC", text):
                blocking.append(prefix + "non-nfc-text")
            if not row.native_reviewer.strip():
                blocking.append(prefix + "native-review-required")
            if not row.terminology_approved:
                blocking.append(prefix + "terminology-not-approved")
            if not row.pronunciation_approved:
                blocking.append(prefix + "pronunciation-not-approved")
            if not row.timing_approved:
                blocking.append(prefix + "timing-not-approved")
            if not row.child_audience_approved:
                blocking.append(prefix + "child-register-not-approved")

            letters = {character.lower() for character in text if character.isalpha()}
            unexpected = sorted(letters - KURMANJI_ALPHABET)
            if unexpected:
                advisory.append(prefix + "manual-script-review:" + "".join(unexpected))

        content = {
            "language": KURMANJI_LANGUAGE,
            "register": self.register,
            "regions": REGIONAL_COVERAGE,
            "lines": [
                {
                    "line_id": row.line_id,
                    "localized_text": unicodedata.normalize("NFC", row.localized_text),
                    "native_reviewer": row.native_reviewer,
                    "terminology_approved": row.terminology_approved,
                    "pronunciation_approved": row.pronunciation_approved,
                    "timing_approved": row.timing_approved,
                    "child_audience_approved": row.child_audience_approved,
                }
                for row in rows
            ],
            "blocking_issues": blocking,
            "advisory_issues": advisory,
        }
        digest = hashlib.sha256(
            json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return KurmanjiQualityReport(
            language=KURMANJI_LANGUAGE,
            register=self.register,
            regions=REGIONAL_COVERAGE,
            line_count=len(rows),
            blocking_issues=tuple(blocking),
            advisory_issues=tuple(advisory),
            ready=not blocking,
            report_hash=digest,
        )

