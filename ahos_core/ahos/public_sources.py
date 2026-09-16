from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .opportunity_intake import (
    OpportunityCandidateStore,
    OpportunityIntakeEngine,
    OpportunitySource,
    SourceKind,
)


def default_public_sources() -> tuple[OpportunitySource, ...]:
    """Public, read-only job feeds used by AHOS.

    These feeds require no login and are only read. AHOS does not apply,
    contact employers, post content, or perform any external write action.
    """
    return (
        OpportunitySource(
            source_id="remoteok-all-rss",
            kind=SourceKind.RSS,
            url="https://remoteok.com/remote-jobs.rss",
            category="remote-work",
        ),
        OpportunitySource(
            source_id="wwr-programming-rss",
            kind=SourceKind.RSS,
            url="https://weworkremotely.com/categories/remote-programming-jobs.rss",
            category="software",
        ),
        OpportunitySource(
            source_id="wwr-devops-rss",
            kind=SourceKind.RSS,
            url="https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
            category="devops",
        ),
    )


@dataclass(frozen=True, slots=True)
class SourceCollectionResult:
    source_id: str
    added_count: int
    error: str | None


@dataclass(frozen=True, slots=True)
class CollectionReport:
    results: tuple[SourceCollectionResult, ...]

    @property
    def added_count(self) -> int:
        return sum(item.added_count for item in self.results)

    @property
    def failures(self) -> tuple[SourceCollectionResult, ...]:
        return tuple(item for item in self.results if item.error is not None)


def collect_public_opportunities(
    root: str | Path,
    *,
    sources: Iterable[OpportunitySource] | None = None,
    fetcher: Callable[[str], bytes] | None = None,
    discovered_at: str | None = None,
) -> CollectionReport:
    """Collect configured sources independently so one bad feed cannot stop all.

    This is read-only network intake. The only write is to the local candidate
    JSONL store.
    """
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    store = OpportunityCandidateStore(root_path / "public_candidates.jsonl")
    engine = OpportunityIntakeEngine(store, fetcher=fetcher)

    results: list[SourceCollectionResult] = []
    for source in tuple(sources or default_public_sources()):
        try:
            added = engine.ingest((source,), discovered_at=discovered_at)
            results.append(
                SourceCollectionResult(
                    source_id=source.source_id,
                    added_count=len(added),
                    error=None,
                )
            )
        except Exception as exc:
            results.append(
                SourceCollectionResult(
                    source_id=source.source_id,
                    added_count=0,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )

    return CollectionReport(tuple(results))
