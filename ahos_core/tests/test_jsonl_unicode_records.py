from __future__ import annotations

from ahos.opportunity_intake import OpportunityCandidate, OpportunityCandidateStore


def test_jsonl_reader_does_not_split_unicode_line_separator(tmp_path) -> None:
    store = OpportunityCandidateStore(tmp_path / "candidates.jsonl")
    candidate = OpportunityCandidate(
        candidate_id="c-1",
        source_id="remoteok-api",
        source_url="https://remoteok.com/api",
        item_url="https://example.test/job/1",
        title="Python Engineer",
        description="first paragraph\u2028second paragraph",
        category="remote-work",
        discovered_at="2026-09-16T12:00:00+00:00",
        raw_metadata={"description": "first paragraph\u2028second paragraph"},
    )

    added = store.append_new((candidate,))
    loaded = store.all()

    assert added == (candidate,)
    assert loaded == (candidate,)
