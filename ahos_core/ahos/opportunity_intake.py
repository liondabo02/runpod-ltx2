from __future__ import annotations

import hashlib
import json
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Any


class SourceKind(str, Enum):
    JSON = "json"
    RSS = "rss"


@dataclass(frozen=True, slots=True)
class OpportunitySource:
    source_id: str
    kind: SourceKind
    url: str
    category: str
    enabled: bool = True
    items_path: str = "items"
    title_field: str = "title"
    url_field: str = "url"
    description_field: str = "description"

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id must not be empty")
        if not self.url.lower().startswith(("http://", "https://")):
            raise ValueError("source url must be http/https")
        if not self.category.strip():
            raise ValueError("category must not be empty")


@dataclass(frozen=True, slots=True)
class OpportunityCandidate:
    candidate_id: str
    source_id: str
    source_url: str
    item_url: str
    title: str
    description: str
    category: str
    discovered_at: str
    raw_metadata: dict[str, Any]


def _stable_candidate_id(source_id: str, item_url: str, title: str) -> str:
    basis = f"{source_id}\n{item_url}\n{title}".encode("utf-8")
    return hashlib.sha256(basis).hexdigest()[:24]


def _nested_get(value: Any, dotted_path: str) -> Any:
    current = value
    for part in [p for p in dotted_path.split(".") if p]:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


class ReadOnlyHttpFetcher:
    """Small read-only HTTP fetcher. It performs GET requests only."""

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds

    def __call__(self, url: str) -> bytes:
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "User-Agent": "AHOS-Opportunity-Intake/1.0",
                "Accept": "application/json, application/rss+xml, application/xml, text/xml, */*",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            return response.read()


class OpportunityCandidateStore:
    """Append-only JSONL store with duplicate protection."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def all(self) -> tuple[OpportunityCandidate, ...]:
        if not self.path.exists():
            return ()

        result: list[OpportunityCandidate] = []
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid opportunity candidate JSON at line {line_number}"
                ) from exc
            result.append(OpportunityCandidate(**raw))
        return tuple(result)

    def ids(self) -> set[str]:
        return {item.candidate_id for item in self.all()}

    def append_new(
        self,
        candidates: Iterable[OpportunityCandidate],
    ) -> tuple[OpportunityCandidate, ...]:
        known = self.ids()
        added: list[OpportunityCandidate] = []

        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            for candidate in candidates:
                if candidate.candidate_id in known:
                    continue
                handle.write(
                    json.dumps(
                        asdict(candidate),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                known.add(candidate.candidate_id)
                added.append(candidate)

        return tuple(added)


class OpportunityIntakeEngine:
    """Read-only opportunity intake from explicitly configured public sources."""

    def __init__(
        self,
        store: OpportunityCandidateStore,
        *,
        fetcher: Callable[[str], bytes] | None = None,
    ) -> None:
        self.store = store
        self.fetcher = fetcher or ReadOnlyHttpFetcher()

    def ingest(
        self,
        sources: Iterable[OpportunitySource],
        *,
        discovered_at: str | None = None,
    ) -> tuple[OpportunityCandidate, ...]:
        when = discovered_at or datetime.now(timezone.utc).isoformat()
        discovered: list[OpportunityCandidate] = []

        for source in sources:
            if not source.enabled:
                continue
            payload = self.fetcher(source.url)
            if source.kind is SourceKind.JSON:
                discovered.extend(self._from_json(source, payload, when))
            elif source.kind is SourceKind.RSS:
                discovered.extend(self._from_rss(source, payload, when))
            else:
                raise ValueError(f"unsupported source kind: {source.kind}")

        return self.store.append_new(discovered)

    def _from_json(
        self,
        source: OpportunitySource,
        payload: bytes,
        when: str,
    ) -> list[OpportunityCandidate]:
        raw = json.loads(payload.decode("utf-8"))
        items = _nested_get(raw, source.items_path) if source.items_path else raw
        if items is None and isinstance(raw, list):
            items = raw
        if not isinstance(items, list):
            raise ValueError(
                f"JSON source {source.source_id} did not return a list at {source.items_path!r}"
            )

        result: list[OpportunityCandidate] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = str(item.get(source.title_field) or "").strip()
            item_url = str(item.get(source.url_field) or source.url).strip()
            description = str(item.get(source.description_field) or "").strip()
            if not title:
                continue
            result.append(
                OpportunityCandidate(
                    candidate_id=_stable_candidate_id(
                        source.source_id, item_url, title
                    ),
                    source_id=source.source_id,
                    source_url=source.url,
                    item_url=item_url,
                    title=title,
                    description=description,
                    category=source.category,
                    discovered_at=when,
                    raw_metadata=item,
                )
            )
        return result

    def _from_rss(
        self,
        source: OpportunitySource,
        payload: bytes,
        when: str,
    ) -> list[OpportunityCandidate]:
        root = ET.fromstring(payload)
        result: list[OpportunityCandidate] = []

        items = root.findall(".//item")
        if not items:
            # Basic Atom support.
            items = root.findall(".//{*}entry")

        for item in items:
            title = (item.findtext("title") or item.findtext("{*}title") or "").strip()

            link = (item.findtext("link") or "").strip()
            if not link:
                link_node = item.find("{*}link")
                if link_node is not None:
                    link = (link_node.attrib.get("href") or "").strip()

            description = (
                item.findtext("description")
                or item.findtext("{*}summary")
                or item.findtext("{*}content")
                or ""
            ).strip()

            if not title:
                continue

            item_url = link or source.url
            result.append(
                OpportunityCandidate(
                    candidate_id=_stable_candidate_id(
                        source.source_id, item_url, title
                    ),
                    source_id=source.source_id,
                    source_url=source.url,
                    item_url=item_url,
                    title=title,
                    description=description,
                    category=source.category,
                    discovered_at=when,
                    raw_metadata={},
                )
            )

        return result
