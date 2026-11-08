from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import re
from typing import Callable, Mapping, Protocol


class GitHubResearchError(RuntimeError):
    pass


class QueryRejectedError(GitHubResearchError):
    pass


class MalformedGitHubResponseError(GitHubResearchError):
    pass


_SAFE_TERM = re.compile(r"^[A-Za-z0-9._+ -]+$")
_FULL_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


@dataclass(frozen=True, slots=True)
class GitHubQuery:
    query_id: str
    terms: tuple[str, ...]
    language: str | None = None
    min_stars: int = 0


@dataclass(frozen=True, slots=True)
class GitHubRepositoryEvidence:
    full_name: str
    html_url: str
    description: str
    default_branch: str
    head_sha: str | None
    license_spdx: str | None
    stars: int
    forks: int
    open_issues: int
    pushed_at: str | None
    collected_at: str
    query_id: str

    def to_payload(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GitHubResearchBatch:
    query: GitHubQuery
    candidates: tuple[GitHubRepositoryEvidence, ...]
    pages_fetched: int
    incomplete_results: bool
    rate_limit_remaining: int | None

    def to_payload(self) -> dict[str, object]:
        return {"schema": "ahos.github-research.v1", "query": asdict(self.query), "candidates": [c.to_payload() for c in self.candidates], "pages_fetched": self.pages_fetched, "incomplete_results": self.incomplete_results, "rate_limit_remaining": self.rate_limit_remaining}


class GitHubReadClient(Protocol):
    def search_repositories(self, *, query: str, page: int, per_page: int) -> Mapping[str, object]: ...
    def branch_head(self, *, full_name: str, branch: str) -> Mapping[str, object]: ...
    def license(self, *, full_name: str) -> Mapping[str, object] | None: ...


class GitHubResearcher:
    def __init__(self, client: GitHubReadClient, *, allowed_terms: frozenset[str], max_pages: int = 3, per_page: int = 30, max_candidates: int = 50, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self.client, self.allowed_terms, self.max_pages = client, allowed_terms, max_pages
        self.per_page, self.max_candidates, self.clock = per_page, max_candidates, clock

    def _render(self, query: GitHubQuery) -> str:
        if not query.query_id or not query.terms or len(query.terms) > 8 or query.min_stars < 0:
            raise QueryRejectedError("invalid query")
        for term in query.terms:
            if term not in self.allowed_terms or not _SAFE_TERM.fullmatch(term) or ":" in term:
                raise QueryRejectedError(f"term not allowed: {term}")
        parts = list(query.terms)
        if query.language:
            if not _SAFE_TERM.fullmatch(query.language) or ":" in query.language:
                raise QueryRejectedError("invalid language")
            parts.append(f"language:{query.language}")
        parts.append(f"stars:>={query.min_stars}")
        return " ".join(parts)

    def discover(self, query: GitHubQuery) -> GitHubResearchBatch:
        rendered, seen, out = self._render(query), set(), []
        pages, incomplete, remaining = 0, False, None
        for page in range(1, self.max_pages + 1):
            raw = self.client.search_repositories(query=rendered, page=page, per_page=self.per_page)
            items = raw.get("items")
            if not isinstance(items, list):
                raise MalformedGitHubResponseError("items must be a list")
            pages += 1
            incomplete = incomplete or bool(raw.get("incomplete_results", False))
            value = raw.get("rate_limit_remaining")
            remaining = int(value) if value is not None else remaining
            for item in items:
                if not isinstance(item, Mapping) or item.get("archived") or item.get("fork"):
                    continue
                full_name = str(item.get("full_name", ""))
                if not _FULL_NAME.fullmatch(full_name):
                    raise MalformedGitHubResponseError("invalid repository name")
                key = full_name.lower()
                if key in seen:
                    continue
                seen.add(key)
                branch = str(item.get("default_branch") or "main")
                head = self.client.branch_head(full_name=full_name, branch=branch).get("sha")
                if head is not None and not _SHA.fullmatch(str(head)):
                    raise MalformedGitHubResponseError("invalid commit sha")
                lic = self.client.license(full_name=full_name) or {}
                out.append(GitHubRepositoryEvidence(full_name, f"https://github.com/{full_name}", str(item.get("description") or ""), branch, str(head) if head else None, str(lic.get("spdx_id")) if lic.get("spdx_id") else None, int(item.get("stargazers_count", 0)), int(item.get("forks_count", 0)), int(item.get("open_issues_count", 0)), str(item.get("pushed_at")) if item.get("pushed_at") else None, self.clock().isoformat(), query.query_id))
                if len(out) >= self.max_candidates:
                    incomplete = True
                    break
            if len(out) >= self.max_candidates or not items or remaining == 0:
                break
        return GitHubResearchBatch(query, tuple(out), pages, incomplete, remaining)
