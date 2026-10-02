from __future__ import annotations

import json

from ahos.opportunity_intake import (
    OpportunityCandidateStore,
    OpportunityIntakeEngine,
    OpportunitySource,
    SourceKind,
)


def test_json_source_ingest_is_read_only_and_deduplicated(tmp_path) -> None:
    calls: list[str] = []

    def fetcher(url: str) -> bytes:
        calls.append(url)
        return json.dumps(
            {
                "items": [
                    {
                        "title": "Build a local automation tool",
                        "url": "https://example.test/jobs/1",
                        "description": "Python automation work",
                    }
                ]
            }
        ).encode("utf-8")

    store = OpportunityCandidateStore(tmp_path / "candidates.jsonl")
    engine = OpportunityIntakeEngine(store, fetcher=fetcher)
    source = OpportunitySource(
        source_id="example-json",
        kind=SourceKind.JSON,
        url="https://example.test/feed.json",
        category="software",
    )

    first = engine.ingest(
        (source,),
        discovered_at="2026-09-16T12:00:00+00:00",
    )
    second = engine.ingest(
        (source,),
        discovered_at="2026-09-16T12:01:00+00:00",
    )

    assert len(first) == 1
    assert len(second) == 0
    assert len(store.all()) == 1
    assert calls == [
        "https://example.test/feed.json",
        "https://example.test/feed.json",
    ]


def test_json_field_mapping_supports_public_api_shapes(tmp_path) -> None:
    def fetcher(_: str) -> bytes:
        return json.dumps(
            {
                "results": [
                    {
                        "name": "Need Python integration",
                        "html_url": "https://example.test/2",
                        "body": "Integrate a public API",
                    }
                ]
            }
        ).encode("utf-8")

    engine = OpportunityIntakeEngine(
        OpportunityCandidateStore(tmp_path / "candidates.jsonl"),
        fetcher=fetcher,
    )
    source = OpportunitySource(
        source_id="mapped-api",
        kind=SourceKind.JSON,
        url="https://example.test/api",
        category="software",
        items_path="results",
        title_field="name",
        url_field="html_url",
        description_field="body",
    )

    added = engine.ingest((source,))

    assert added[0].title == "Need Python integration"
    assert added[0].item_url == "https://example.test/2"


def test_rss_ingest(tmp_path) -> None:
    rss = b"""<?xml version="1.0"?>
    <rss><channel>
      <item>
        <title>Automation contract</title>
        <link>https://example.test/rss/1</link>
        <description>Small automation job</description>
      </item>
    </channel></rss>"""

    engine = OpportunityIntakeEngine(
        OpportunityCandidateStore(tmp_path / "candidates.jsonl"),
        fetcher=lambda _: rss,
    )
    source = OpportunitySource(
        source_id="example-rss",
        kind=SourceKind.RSS,
        url="https://example.test/feed.xml",
        category="software",
    )

    added = engine.ingest((source,))

    assert len(added) == 1
    assert added[0].title == "Automation contract"


def test_disabled_source_is_not_fetched(tmp_path) -> None:
    def fetcher(_: str) -> bytes:
        raise AssertionError("disabled source must not be fetched")

    engine = OpportunityIntakeEngine(
        OpportunityCandidateStore(tmp_path / "candidates.jsonl"),
        fetcher=fetcher,
    )
    source = OpportunitySource(
        source_id="disabled",
        kind=SourceKind.JSON,
        url="https://example.test/feed.json",
        category="software",
        enabled=False,
    )

    assert engine.ingest((source,)) == ()
