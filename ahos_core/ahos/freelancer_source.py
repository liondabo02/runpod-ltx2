from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from .opportunity_intake import OpportunityCandidate


SearchCallable = Callable[[str, int], Any]


@dataclass(frozen=True, slots=True)
class FreelancerSearchConfig:
    query: str
    limit: int = 50

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("query must not be empty")
        if not 1 <= self.limit <= 100:
            raise ValueError("limit must be between 1 and 100")


def _project_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("projects", "result", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
        if isinstance(payload.get("result"), dict):
            nested = payload["result"]
            for key in ("projects", "items"):
                value = nested.get(key)
                if isinstance(value, list):
                    return [row for row in value if isinstance(row, dict)]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _project_url(project: dict[str, Any]) -> str:
    if project.get("seo_url"):
        seo = str(project["seo_url"]).lstrip("/")
        if seo.startswith("http://") or seo.startswith("https://"):
            return seo
        return "https://www.freelancer.com/projects/" + seo
    project_id = project.get("id")
    if project_id:
        return f"https://www.freelancer.com/projects/{project_id}"
    return "https://www.freelancer.com/jobs/"


def _budget_text(project: dict[str, Any]) -> str:
    budget = project.get("budget")
    if not isinstance(budget, dict):
        return ""
    minimum = budget.get("minimum")
    maximum = budget.get("maximum")
    if minimum is None and maximum is None:
        return ""
    return f"Budget: {minimum or ''}-{maximum or ''}".strip("-")


class FreelancerProjectAdapter:
    """Read-only adapter for Freelancer.com project search.

    The live SDK path is loaded only when search_live() is called. Tests and
    local validation can inject a fake search callable and require no network.
    """

    def __init__(self, search: SearchCallable | None = None) -> None:
        self._search = search

    def search(
        self,
        config: FreelancerSearchConfig,
        *,
        discovered_at: str | None = None,
    ) -> tuple[OpportunityCandidate, ...]:
        if self._search is None:
            raise RuntimeError("no search callable configured")
        payload = self._search(config.query, config.limit)
        when = discovered_at or datetime.now(timezone.utc).isoformat()
        candidates: list[OpportunityCandidate] = []

        for project in _project_rows(payload):
            title = str(project.get("title") or "").strip()
            if not title:
                continue

            description = str(
                project.get("description")
                or project.get("preview_description")
                or ""
            ).strip()
            budget = _budget_text(project)
            if budget:
                description = (description + "\n" + budget).strip()

            project_id = str(project.get("id") or "")
            item_url = _project_url(project)

            candidates.append(
                OpportunityCandidate(
                    candidate_id=f"freelancer-project-{project_id or abs(hash(item_url))}",
                    source_id="freelancer-api",
                    source_url="https://www.freelancer.com/",
                    item_url=item_url,
                    title=title,
                    description=description,
                    category="freelance-project",
                    discovered_at=when,
                    raw_metadata=project,
                )
            )
        return tuple(candidates)

    @classmethod
    def live(cls, oauth_token: str) -> "FreelancerProjectAdapter":
        if not oauth_token.strip():
            raise ValueError("Freelancer OAuth token is required")

        try:
            from freelancersdk.session import Session
            from freelancersdk.resources.projects.projects import search_projects
            from freelancersdk.resources.projects.helpers import (
                create_search_projects_filter,
            )
        except ImportError as exc:
            raise RuntimeError(
                "freelancersdk is not installed. Install it before live use."
            ) from exc

        session = Session(oauth_token=oauth_token)

        def _search(query: str, limit: int) -> Any:
            search_filter = create_search_projects_filter(
                sort_field="time_updated",
                or_search_query=True,
            )
            return search_projects(
                session,
                query=query,
                search_filter=search_filter,
                limit=limit,
                active_only=True,
            )

        return cls(search=_search)
