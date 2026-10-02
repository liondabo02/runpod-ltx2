from __future__ import annotations

from ahos.freelancer_source import FreelancerProjectAdapter, FreelancerSearchConfig


def test_fake_project_search_converts_projects_to_candidates() -> None:
    def fake_search(query: str, limit: int):
        assert query == "python automation"
        assert limit == 25
        return {
            "projects": [
                {
                    "id": 123,
                    "title": "Python API automation project",
                    "description": "Build an API integration and automation workflow.",
                    "seo_url": "python-api-automation-project",
                    "budget": {"minimum": 100, "maximum": 500},
                }
            ]
        }

    adapter = FreelancerProjectAdapter(search=fake_search)
    items = adapter.search(
        FreelancerSearchConfig("python automation", limit=25),
        discovered_at="2026-09-16T12:00:00+00:00",
    )

    assert len(items) == 1
    assert items[0].source_id == "freelancer-api"
    assert items[0].category == "freelance-project"
    assert items[0].title == "Python API automation project"
    assert "Budget:" in items[0].description
    assert "freelancer.com/projects/" in items[0].item_url


def test_nested_result_shape_is_supported() -> None:
    adapter = FreelancerProjectAdapter(
        search=lambda _query, _limit: {
            "result": {
                "projects": [
                    {
                        "id": 456,
                        "title": "Automation contractor",
                        "preview_description": "Integrate services.",
                    }
                ]
            }
        }
    )

    items = adapter.search(FreelancerSearchConfig("automation"))
    assert [item.title for item in items] == ["Automation contractor"]


def test_empty_query_is_rejected() -> None:
    try:
        FreelancerSearchConfig("   ")
    except ValueError as exc:
        assert "query must not be empty" in str(exc)
    else:
        raise AssertionError("empty query must fail")
