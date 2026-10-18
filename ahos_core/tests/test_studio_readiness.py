import json

from ahos.studio_readiness import CAPABILITIES, build_readiness_report, human_summary, main


def make_project(tmp_path):
    (tmp_path / "ahos").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    for item in CAPABILITIES:
        (tmp_path / "ahos" / item.module).write_text("# implementation\n", encoding="utf-8")
        (tmp_path / "tests" / item.test).write_text("# tests\n", encoding="utf-8")
    return tmp_path


def test_capability_score_requires_both_module_and_test(tmp_path):
    project = make_project(tmp_path)
    missing = CAPABILITIES[0]
    (project / "tests" / missing.test).unlink()

    report = build_readiness_report(project)

    score = report["score_definition"]
    assert score["earned"] == 100 - missing.weight
    assert score["possible"] == 100
    row = next(item for item in report["capabilities"] if item["capability_id"] == missing.capability_id)
    assert row["status"] == "missing_evidence"
    assert row["missing"] == ["focused_tests"]
    assert report["episode"]["release_ready"] is False


def test_episode_readiness_fails_closed_and_preserves_department_state(tmp_path):
    project = make_project(tmp_path / "project")
    studio = tmp_path / "episode"
    artifacts = studio / "artifacts"
    artifacts.mkdir(parents=True)
    for name in ("episode.json", "continuity-clearance.json", "production-graph.json", "render-jobs.json", "voice-casting.json", "localization-plan.json"):
        (artifacts / name).write_text("{}", encoding="utf-8")
    (studio / "OWNER-APPROVAL.json").write_text(json.dumps({
        "episode_id": "S01E003",
        "owner_approved": False,
        "paid_execution_enabled": False,
        "evidence": {"department_statuses": [{"department": "render", "status": "waiting_owner_approval"}]},
    }), encoding="utf-8")

    report = build_readiness_report(project, studio_directory=studio)

    episode = report["episode"]
    assert episode["release_ready"] is False
    assert episode["checks"]["planning_artifacts"] is True
    assert "owner_approved" in episode["blockers"]
    assert episode["departments"][0]["status"] == "waiting_owner_approval"
    assert "Episode release ready: NO" in human_summary(report)


def test_episode_is_ready_only_with_all_concrete_evidence(tmp_path):
    project = make_project(tmp_path / "project")
    studio = tmp_path / "episode"
    artifacts = studio / "artifacts"
    artifacts.mkdir(parents=True)
    for name in ("episode.json", "continuity-clearance.json", "production-graph.json", "render-jobs.json", "voice-casting.json", "localization-plan.json"):
        (artifacts / name).write_text("{}", encoding="utf-8")
    (artifacts / "final.mp4").write_bytes(b"media")
    (studio / "OWNER-APPROVAL.json").write_text(json.dumps({"owner_approved": True, "paid_execution_enabled": True}), encoding="utf-8")
    (studio / "EXECUTION-PREFLIGHT.json").write_text(json.dumps({"approval_ready": True}), encoding="utf-8")
    (studio / "studio-report.json").write_text(json.dumps({"release_ready": True}), encoding="utf-8")

    report = build_readiness_report(project, studio_directory=studio)

    assert report["episode"]["release_ready"] is True
    assert report["episode"]["blockers"] == []


def test_cli_writes_machine_readable_report(tmp_path, capsys):
    project = make_project(tmp_path / "project")
    output = tmp_path / "readiness.json"
    assert main(["--project-dir", str(project), "--json", "--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["schema"] == "ahos.studio-readiness.v1"
    assert json.loads(capsys.readouterr().out)["score_definition"]["earned"] == 100
