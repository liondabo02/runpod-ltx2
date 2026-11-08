from control_plane.agents import AGENTS
from control_plane.preflight import check


def test_preflight_reports_missing_routes(monkeypatch):
    for spec in AGENTS.values():
        monkeypatch.delenv(spec.model_env, raising=False)
    result = check()
    assert result.ready is False
    assert set(result.missing_roles) == set(AGENTS)


def test_preflight_accepts_five_distinct_routes(monkeypatch):
    routes = {
        'supervisor': 'openai/example-supervisor',
        'github_scout': 'openrouter/example-scout',
        'builder': 'anthropic/example-builder',
        'qa_sre': 'novita/example-qa',
        'cost_security': 'ollama/example-local',
    }
    for role, spec in AGENTS.items():
        monkeypatch.setenv(spec.model_env, routes[role])
    result = check()
    assert result.ready is True
    assert result.missing_roles == ()
    assert set(result.configured_providers) == {'openai', 'openrouter', 'anthropic', 'novita', 'ollama'}
