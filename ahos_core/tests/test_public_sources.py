from __future__ import annotations

from ahos.opportunity_intake import OpportunitySource, SourceKind
from ahos.public_sources import collect_public_opportunities, default_public_sources


def test_default_sources_are_public_https_read_only_feeds() -> None:
    sources = default_public_sources()

    assert len(sources) >= 3
    assert all(source.enabled for source in sources)
    assert all(source.kind is SourceKind.RSS for source in sources)
    assert all(source.url.startswith("https://") for source in sources)
    assert {source.source_id for source in sources} >= {
        "remoteok-all-rss",
        "wwr-programming-rss",
        "wwr-devops-rss",
    }


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
    assert first.failures == ()


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
