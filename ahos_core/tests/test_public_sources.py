from __future__ import annotations

import json

from ahos.opportunity_intake import OpportunitySource, SourceKind
from ahos.public_sources import collect_public_opportunities, default_public_sources


def test_default_sources_use_remoteok_json_and_wwr_rss() -> None:
    sources = default_public_sources()
    by_id = {source.source_id: source for source in sources}

    assert len(sources) >= 3
    assert all(source.enabled for source in sources)
    assert by_id["remoteok-api"].kind is SourceKind.JSON
    assert by_id["remoteok-api"].url == "https://remoteok.com/api"
    assert by_id["remoteok-api"].title_field == "position"
    assert by_id["remoteok-api"].url_field == "url"

    assert by_id["wwr-programming-rss"].kind is SourceKind.RSS
    assert by_id["wwr-devops-rss"].kind is SourceKind.RSS
    assert all(source.url.startswith("https://") for source in sources)


def test_remoteok_json_shape_is_supported(tmp_path) -> None:
    payload = json.dumps(
        [
            {"legal": "terms"},
            {
                "position": "Python Automation Engineer",
                "url": "https://remoteok.com/remote-jobs/example",
                "description": "Build Python automation.",
                "company": "Example Co",
                "salary_min": 50000,
                "salary_max": 70000,
            },
        ]
    ).encode("utf-8")

    source = next(
        source
        for source in default_public_sources()
        if source.source_id == "remoteok-api"
    )

    report = collect_public_opportunities(
        tmp_path,
        sources=(source,),
        fetcher=lambda _: payload,
        discovered_at="2026-09-16T12:00:00+00:00",
    )

    assert report.added_count == 1
    assert report.failures == ()


def test_collection_uses_injected_fetcher_and_deduplicates(tmp_path) -> None:
    rss = b"""<?xml version="1.0"?>
    <rss><channel>
      <item>
        <title>Python automation contractor</title>
        <link>https://example.test/job/1</link>
        <description>Build a small automation system</description>
      </item>
    </channel></rss>"""

    source = OpportunitySource(
        source_id="test-feed",
        kind=SourceKind.RSS,
        url="https://example.test/jobs.rss",
        category="software",
    )

    first = collect_public_opportunities(
        tmp_path,
        sources=(source,),
        fetcher=lambda _: rss,
        discovered_at="2026-09-16T12:00:00+00:00",
    )
    second = collect_public_opportunities(
        tmp_path,
        sources=(source,),
        fetcher=lambda _: rss,
        discovered_at="2026-09-16T12:01:00+00:00",
    )

    assert first.added_count == 1
    assert second.added_count == 0


def test_one_failed_source_does_not_block_other_sources(tmp_path) -> None:
    good_rss = b"""<?xml version="1.0"?>
    <rss><channel>
      <item>
        <title>Good opportunity</title>
        <link>https://good.test/job/1</link>
        <description>Good feed</description>
      </item>
    </channel></rss>"""

    bad = OpportunitySource(
        source_id="bad",
        kind=SourceKind.RSS,
        url="https://bad.test/jobs.rss",
        category="software",
    )
    good = OpportunitySource(
        source_id="good",
        kind=SourceKind.RSS,
        url="https://good.test/jobs.rss",
        category="software",
    )

    def fetcher(url: str) -> bytes:
        if "bad.test" in url:
            raise RuntimeError("feed unavailable")
        return good_rss

    report = collect_public_opportunities(
        tmp_path,
        sources=(bad, good),
        fetcher=fetcher,
    )

    assert report.added_count == 1
    assert len(report.failures) == 1
    assert report.failures[0].source_id == "bad"
