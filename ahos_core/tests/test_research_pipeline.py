from datetime import UTC, datetime
import hashlib

import pytest

from ahos.github_research import GitHubQuery, GitHubResearcher, QueryRejectedError
from ahos.integration_proposal import IntegrationProposalBuilder, IntegrationRisk, ProposalStatus
from ahos.research_store import ResearchEvidence, ResearchIntegrityError, ResearchStore
from ahos.technology_evaluation import EvaluationRecommendation, TechnologyEvaluator, TechnologySignals


class FakeGitHub:
    def search_repositories(self, **kwargs):
        return {"items": [{"full_name": "org/tool", "default_branch": "main", "stargazers_count": 10, "forks_count": 2, "open_issues_count": 1}], "rate_limit_remaining": 10}
    def branch_head(self, **kwargs): return {"sha": "a" * 40}
    def license(self, **kwargs): return {"spdx_id": "MIT"}


def test_read_only_discovery_and_injection_rejection():
    researcher = GitHubResearcher(FakeGitHub(), allowed_terms=frozenset({"agents"}), max_pages=1, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    batch = researcher.discover(GitHubQuery("q1", ("agents",)))
    assert batch.candidates[0].head_sha == "a" * 40
    with pytest.raises(QueryRejectedError): researcher.discover(GitHubQuery("bad", ("repo:evil/x",)))


def test_evaluator_never_auto_adopts_and_fails_closed():
    repo = GitHubResearcher(FakeGitHub(), allowed_terms=frozenset({"agents"}), max_pages=1).discover(GitHubQuery("q", ("agents",))).candidates[0]
    clean = TechnologySignals(repo, 5, 0, True, True, True, False, 95)
    result = TechnologyEvaluator().evaluate(technology_id="tool", signals=clean)
    assert result.recommendation is EvaluationRecommendation.TRIAL
    assert result.eligible_for_sandbox_proposal is True
    blocked = TechnologyEvaluator().evaluate(technology_id="tool", signals=TechnologySignals(repo, 5, None, None, None, None, None, 95))
    assert blocked.recommendation is EvaluationRecommendation.REJECT


def test_store_is_append_only_idempotent_and_tamper_evident(tmp_path):
    path = tmp_path / "research.jsonl"; store = ResearchStore(path)
    evidence = ResearchEvidence("e1", "r1", "https://github.com/org/tool", "a" * 40, "MIT", "research-01", "2026-01-01T00:00:00Z", hashlib.sha256(b"x").hexdigest())
    store.append(evidence); store.append(evidence)
    assert len(store.list()) == 1
    path.write_text(path.read_text().replace("MIT", "GPL-3.0-only"), encoding="utf-8")
    with pytest.raises(ResearchIntegrityError): store.verify_integrity()


def test_proposal_remains_inert_and_waiting(tmp_path):
    store = ResearchStore(tmp_path / "research.jsonl")
    store.append(ResearchEvidence("e1", "r1", "https://github.com/org/tool", "a" * 40, "MIT", "research-01", "2026-01-01T00:00:00Z", hashlib.sha256(b"x").hexdigest()))
    proposal = IntegrationProposalBuilder(store).build(proposal_id="p1", research_id="r1", evidence_ids=("e1",), title="Trial", target_department="software", proposed_by="research-01", summary="Sandbox only", risk=IntegrationRisk.LOW, estimated_cost_usd=0.0, external_side_effect=False, destructive=False, touches_secrets=False, tests=("pytest",), rollback_plan="Disable feature flag")
    assert proposal.status is ProposalStatus.WAITING_OWNER_APPROVAL
