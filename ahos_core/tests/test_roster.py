from __future__ import annotations

import json

from ahos.model_planner import build_context
from ahos.report import collect, render
from ahos.roster import build_roster, render as render_roster


def _runtime(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "departments.json").write_text(
        json.dumps(
            {
                "version": 1,
                "departments": [
                    {
                        "department_id": "oyun",
                        "name": "Oyun Geliştirme",
                        "mission": "çocuk oyunları",
                        "capabilities": [{"name": "game_design"}, {"name": "qa"}],
                        "status": "active",
                        "workers": [
                            {
                                "worker_id": "oyun-manager",
                                "name": "Oyun Müdürü",
                                "role": "manager",
                                "capabilities": ["planning", "routing"],
                                "reports_to": "oyun",
                                "authority_level": 2,
                            },
                            {
                                "worker_id": "oyun-dev",
                                "name": "Geliştirici",
                                "role": "engineer",
                                "capabilities": [{"name": "javascript"}],
                                "reports_to": "oyun-manager",
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (runtime / "daemon-state.json").write_text(
        json.dumps({"pid": 42, "ticks": 7, "status": "running", "executor_mode": "model"}),
        encoding="utf-8",
    )
    return runtime


def test_roster_has_departments_workers_and_reporting_lines(tmp_path) -> None:
    roster = build_roster(_runtime(tmp_path))

    by_id = {card["id"]: card for card in roster["agents"]}

    assert by_id["oyun"]["kind"] == "department"
    assert by_id["oyun-manager"]["reports_to"] == "oyun"
    assert by_id["oyun-dev"]["reports_to"] == "oyun-manager"
    assert by_id["oyun-dev"]["capabilities"] == ["javascript"]
    assert by_id["daemon"]["kind"] == "infrastructure"
    assert "oyun-manager" in by_id["oyun-dev"]["peers"]
    assert roster["summary"]["by_kind"]["department"] == 1
    assert roster["summary"]["by_kind"]["worker"] == 2
    assert {"from": "oyun-dev", "to": "oyun-manager", "kind": "reports_to"} in roster["edges"]


def test_roster_render_lists_every_agent(tmp_path) -> None:
    text = render_roster(build_roster(_runtime(tmp_path)))

    assert "oyun" in text and "oyun-manager" in text and "daemon" in text
    assert "AJAN KAYDI" in text


def test_status_report_includes_the_agent_count(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    report = collect(runtime)
    text = render(report)

    assert report["agents"]["total"] == 5, "departman + 2 işçi + daemon + kalite kapısı"
    assert "ajanlar" in text and "worker=2" in text


def test_planner_context_lists_the_team(tmp_path) -> None:
    context = build_context(
        {"oyun": "Oyun Geliştirme"},
        {"oyun": ["mipiluna"]},
        ["önceki iş"],
        agents={"oyun": ["game_design", "qa"], "oyun-manager": ["planning"]},
    )

    assert "Ekip" in context
    assert "oyun-manager: planning" in context
