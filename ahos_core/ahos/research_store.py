from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re

_SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")
_SHA64 = re.compile(r"^[0-9a-fA-F]{64}$")


class ResearchIntegrityError(RuntimeError): pass


@dataclass(frozen=True, slots=True)
class ResearchEvidence:
    evidence_id: str
    research_id: str
    source_url: str
    source_commit: str
    license_spdx: str
    collected_by: str
    collected_at: str
    content_sha256: str
    notes: str = ""

    def __post_init__(self) -> None:
        if not all((self.evidence_id, self.research_id, self.source_url, self.license_spdx, self.collected_by, self.collected_at)) or not _SHA40.fullmatch(self.source_commit) or not _SHA64.fullmatch(self.content_sha256):
            raise ValueError("invalid research evidence")


class ResearchStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _records(self) -> list[dict[str, object]]:
        if not self.path.exists(): return []
        records, previous = [], "0" * 64
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try: record = json.loads(line)
            except json.JSONDecodeError as exc: raise ResearchIntegrityError("malformed store") from exc
            body = record.get("body")
            canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            expected = hashlib.sha256((previous + canonical).encode()).hexdigest()
            if record.get("previous_hash") != previous or record.get("record_hash") != expected: raise ResearchIntegrityError("hash chain mismatch")
            previous, records = expected, records + [record]
        return records

    def append(self, evidence: ResearchEvidence) -> ResearchEvidence:
        records = self._records()
        for record in records:
            existing = ResearchEvidence(**record["body"])
            if existing.evidence_id == evidence.evidence_id:
                if existing == evidence: return existing
                raise ValueError("conflicting evidence id")
        previous = records[-1]["record_hash"] if records else "0" * 64
        body = asdict(evidence)
        canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        record = {"previous_hash": previous, "body": body, "record_hash": hashlib.sha256((previous + canonical).encode()).hexdigest()}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle: handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        return evidence

    def list(self, research_id: str | None = None) -> tuple[ResearchEvidence, ...]:
        values = tuple(ResearchEvidence(**r["body"]) for r in self._records())
        return tuple(v for v in values if research_id is None or v.research_id == research_id)

    def get(self, evidence_id: str) -> ResearchEvidence | None:
        return next((e for e in self.list() if e.evidence_id == evidence_id), None)

    def verify_integrity(self) -> bool:
        self._records(); return True
