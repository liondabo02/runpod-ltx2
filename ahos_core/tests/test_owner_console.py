from __future__ import annotations

import pytest

from ahos.autonomous_company import QueueStatus
from ahos.departments import DepartmentSpec
from ahos.owner_console import (
    CommandKind,
    ConsoleResult,
    OwnerCommandError,
    OwnerConsole,
    build_default_console,
    make_artifact_executor,
    parse_owner_command,
)
from ahos.mission_orchestrator import MissionStatus


@pytest.fixture()
def console(tmp_path) -> OwnerConsole:
    return build_default_console(tmp_path)


@pytest.mark.parametrize(
    "text",
    (
        "çizgi film departmanı kur",
        "yazılım şirketi kur",
        "yeni bir animasyon stüdyosu aç",
        "build a cartoon company",
        "satış ekibi oluştur",
    ),
)
def test_create_department_intents(text: str) -> None:
    command = parse_owner_command(text)

    assert command.kind is CommandKind.CREATE_DEPARTMENT


@pytest.mark.parametrize(
    "text",
    (
        "bana bir landing page yap",
        "episode 3 için senaryo hazırla",
        "müşteri teklifini yaz",
        "fix the login bug",
    ),
)
def test_task_intents(text: str) -> None:
    command = parse_owner_command(text)

    assert command.kind is CommandKind.TASK


@pytest.mark.parametrize("text", ("durum", "rapor", "status", "özet"))
def test_status_intents(text: str) -> None:
    assert parse_owner_command(text).kind is CommandKind.STATUS


def test_help_intent_and_empty_command() -> None:
    assert parse_owner_command("yardım").kind is CommandKind.HELP

    with pytest.raises(OwnerCommandError):
        parse_owner_command("   ")


def test_creating_a_cartoon_department_registers_and_staffs_it(console) -> None:
    result = console.handle("çizgi film departmanı kur")

    assert isinstance(result, ConsoleResult)
    assert result.ok
    assert result.status == "department_created"
    assert result.department_id == "creative"
    spec = console.book.require("creative")
    assert spec.name == "Çizgi Film Stüdyosu"
    assert len(spec.workers) == 15

    # Kuruluş misyonu gerçek bir kabul doğrulayıcısı olmadan ilerlemez:
    # brief çıktısı üretilir, ancak QA fail-closed olduğu için görev blocked.
    artifacts = list((console.artifacts_root).rglob("deliverable.md"))
    assert len(artifacts) >= 1
    assert result.mission.status is MissionStatus.BLOCKED
    assert any(token in result.mission.reason for token in ("blocked-unverified", "executor_unavailable", "belge kabulü"))


def test_department_survives_a_console_restart(tmp_path) -> None:
    first = build_default_console(tmp_path)
    first.handle("çizgi film departmanı kur")

    second = build_default_console(tmp_path)

    assert second.book.require("creative").name == "Çizgi Film Stüdyosu"
    assert (tmp_path / "departments.json").exists()


def test_task_routes_to_an_existing_department(tmp_path) -> None:
    console = build_default_console(tmp_path)
    console.handle("çizgi film departmanı kur")

    result = console.handle("çizgi film için yeni bir bölüm senaryosu yaz")

    # Kod projesi olmayan şirket, işi belge olarak teslim eder (kabulden geçer).
    assert result.status == "routed"
    assert result.department_id == "creative"
    assert "teslimat:" in result.message
    assert list((tmp_path / "companies").glob("*/plan.md")), "iş belgesi yazılmalı"


def test_task_without_a_matching_department_creates_one_first(tmp_path) -> None:
    console = build_default_console(tmp_path)
    before = len(console.book.all())

    result = console.handle("bir çizgi film bölümü için seslendirme planı hazırla")

    assert result.status in {"routed", "blocked"}
    assert len(console.book.all()) >= before
    assert (tmp_path / "companies").exists(), "şirket/tedarik belgesi yazılmalı"


def test_status_report_lists_departments(console) -> None:
    result = console.handle("durum")

    assert result.status == "status_report"
    assert "departman" in result.message.lower()
    assert "software" in result.message


def test_help_is_returned_for_help_commands(console) -> None:
    result = console.handle("yardım")

    assert result.status == "help"
    assert "departman" in result.message


def test_artifacts_are_written_per_step(tmp_path) -> None:
    from ahos.workforce_execution import WorkItem

    executor = make_artifact_executor(tmp_path / "artifacts")
    item = WorkItem(
        task_id="M-1:produce",
        title="Üretim adımı",
        department="software",
        required_capabilities=frozenset({"python"}),
    )

    result = executor(item, "software-engineer")

    assert result.success is False
    assert result.artifacts
    path = tmp_path / "artifacts" / "M-1_produce" / "deliverable.md"
    assert path.exists()
    assert "software-engineer" in path.read_text(encoding="utf-8")


def test_console_never_raises_on_unexpected_input(console) -> None:
    result = console.handle("!! ?? 123")

    assert isinstance(result, ConsoleResult)
    assert result.status in {"routed", "blocked", "error", "department_created"}


def test_building_a_company_twice_is_idempotent(tmp_path) -> None:
    console = build_default_console(tmp_path)

    first = console.handle("yazılım şirketi kur")
    second = console.handle("yazılım şirketi kur")

    assert first.department_id == "software"
    assert second.department_id == "software"
    assert second.status == "department_created"
    assert "zaten kurulu" in second.message


def test_control_center_exposes_a_command_box_and_departments(tmp_path) -> None:
    from ahos.control_center import ControlCenterState, render_dashboard

    state = ControlCenterState(tmp_path)
    snapshot = state.snapshot()

    assert snapshot["departments"]
    html = render_dashboard(snapshot)
    assert 'action="/action/command"' in html
    assert "Sahip Komutu" in html
    assert "Departmanlar" in html


def test_control_center_runs_and_journals_owner_commands(tmp_path) -> None:
    from ahos.control_center import ControlCenterState

    state = ControlCenterState(tmp_path)
    message = state.handle_command("çizgi film departmanı kur")

    assert "Çizgi Film" in message
    last = state.last_command()
    assert last is not None
    assert last["command"] == "çizgi film departmanı kur"
    assert last["status"] == "department_created"
    assert (tmp_path / "owner-commands.jsonl").exists()
    assert state.console.book.require("creative").name == "Çizgi Film Stüdyosu"

def test_owner_missions_are_persisted_in_the_shared_queue(tmp_path) -> None:
    console = build_default_console(tmp_path)

    result = console.handle("çizgi film departmanı kur")

    queue = console.queue
    assert queue is not None
    missions = queue.list()
    assert missions
    recorded = [m for m in missions if m.primary_department == "creative"]
    assert recorded
    latest = recorded[-1]
    assert latest.status is QueueStatus.BLOCKED
    assert latest.result_json
    assert result.mission is not None
    assert result.mission.mission_id == latest.mission_id


def test_queue_records_blocked_missions_without_losing_them(tmp_path) -> None:
    console = build_default_console(tmp_path)
    console.book.pause("quality")

    result = console.handle("yazılım şirketi kur")

    assert result.status == "department_created"
    missions = [
        m for m in console.queue.list() if m.primary_department == "software"
    ]
    assert missions
    assert missions[-1].status is QueueStatus.BLOCKED
    assert missions[-1].last_error


def test_panel_mission_table_lists_owner_commands(tmp_path) -> None:
    from ahos.control_center import ControlCenterState

    state = ControlCenterState(tmp_path)
    state.handle_command("yazılım şirketi kur")

    snapshot = state.snapshot()
    owner_missions = [
        mission for mission in snapshot["missions"]
        if str(mission["mission_id"]).startswith("CMD-")
    ]

    assert owner_missions
    assert owner_missions[0]["department"] == "software"
    assert owner_missions[0]["status"] in {"completed", "blocked"}

def test_attach_project_intent_is_recognised() -> None:
    from ahos.owner_console import CommandKind, parse_owner_command

    command = parse_owner_command("Mipiluna projesini oyun departmanına bağla")

    assert command.kind is CommandKind.ATTACH_PROJECT
    assert command.text.startswith("Mipiluna")


def test_attach_project_links_a_real_folder(tmp_path) -> None:
    fixture = tmp_path / "sources" / "Mipiluna-22"
    (fixture / "android").mkdir(parents=True)
    (fixture / "index.html").write_text("<html>oyun</html>", encoding="utf-8")
    (fixture / "README.md").write_text("# Mipiluna", encoding="utf-8")
    (fixture / "android" / "build.gradle").write_text("android {}", encoding="utf-8")

    console = build_default_console(tmp_path / "runtime")
    console.project_roots = (tmp_path / "sources",)
    console.handle("oyun geliştirme departmanı kur")

    result = console.handle("Mipiluna projesini oyun departmanına bağla")

    assert result.status == "project_linked"
    assert result.department_id == "oyun"
    assert "Mipiluna" in result.message

    link = console.projects.require("mipiluna")
    assert link.department_id == "oyun"
    assert (link.path / "index.html").exists()

    project_dir = tmp_path / "runtime" / "projects" / "mipiluna"
    plan = (project_dir / "INTEGRATION_PLAN.md").read_text(encoding="utf-8")
    assert "Entegrasyon Planı" in plan
    assert "Mipiluna" in plan
    assert (project_dir / "PROJECT_AUDIT.md").exists()


def test_attach_project_without_source_reports_a_clear_error(tmp_path) -> None:
    console = build_default_console(tmp_path / "runtime")
    console.project_roots = (tmp_path / "empty",)
    (tmp_path / "empty").mkdir()
    console.handle("oyun geliştirme departmanı kur")

    result = console.handle("Mipiluna projesini oyun departmanına bağla")

    assert result.status == "error"
    assert "kaynak bulunamadı" in result.message


def test_create_department_grows_an_existing_smaller_department_in_place(tmp_path) -> None:
    from ahos.departments import CapabilitySpec, DepartmentSpec, WorkerSpec

    console = build_default_console(tmp_path)
    small = DepartmentSpec(
        department_id="oyun",
        name="Oyun Stüdyosu",
        mission="Küçük oyun ekibi.",
        capabilities=(
            CapabilitySpec("oyun.game_design", "tasarım"),
            CapabilitySpec("oyun.testing", "test"),
        ),
        workers=(
            WorkerSpec(
                worker_id="oyun-manager",
                name="Müdür",
                role="department_manager",
                team_id="oyun-leadership",
                capabilities=frozenset({"planning", "game_design", "testing"}),
                reports_to=None,
            ),
            WorkerSpec(
                worker_id="oyun-designer",
                name="Tasarımcı",
                role="researcher",
                team_id="oyun-design",
                capabilities=frozenset({"game_design"}),
                reports_to="oyun-manager",
            ),
        ),
        source="owner-command",
    )
    console.book.add(small, replace=True)

    result = console.handle("oyun geliştirme departmanı kur")

    grown = console.book.require("oyun")
    assert result.department_id == "oyun"
    assert len(grown.workers) > 3
    assert grown.name == "Oyun Geliştirme Departmanı"

def test_panel_lists_linked_projects(tmp_path) -> None:
    from ahos.control_center import ControlCenterState, render_dashboard

    sources = tmp_path / "sources" / "Mipiluna-22"
    (sources / "www").mkdir(parents=True)
    (sources / "www" / "index.html").write_text("<html></html>", encoding="utf-8")
    (sources / "package.json").write_text('{"scripts": {"build": "x"}}', encoding="utf-8")

    state = ControlCenterState(tmp_path / "runtime")
    state.console.project_roots = (tmp_path / "sources",)
    state.handle_command("oyun geliştirme departmanı kur")
    state.handle_command("Mipiluna projesini oyun departmanına bağla")

    snapshot = state.snapshot()
    assert snapshot["projects"]
    assert snapshot["projects"][0]["project_id"] == "mipiluna"
    assert snapshot["projects"][0]["department_id"] == "oyun"

    page = render_dashboard(snapshot)
    assert "Projeler" in page
    assert "mipiluna" in page

def test_foundry_project_command_is_not_mistaken_for_create() -> None:
    from ahos.owner_console import CommandKind, parse_owner_command

    command = parse_owner_command(
        "harun-ai-foundry projesini ai platform departmanına bağla"
    )

    assert command.kind is CommandKind.ATTACH_PROJECT


def test_english_create_verbs_require_exact_token() -> None:
    from ahos.owner_console import CommandKind, parse_owner_command

    assert parse_owner_command("cartoon department create").kind is CommandKind.CREATE_DEPARTMENT
    # "foundry" bir fiil değil; proje bağlama olarak kalmalı
    assert (
        parse_owner_command("foundry projesini bağla").kind
        is CommandKind.ATTACH_PROJECT
    )

def test_project_can_be_linked_in_place(tmp_path, monkeypatch) -> None:
    source = tmp_path / "sources" / "BigRepo"
    (source / "app").mkdir(parents=True)
    (source / "app" / "main.py").write_text("print(1)\n", encoding="utf-8")

    monkeypatch.setenv("AHOS_PROJECT_IN_PLACE", "1")
    console = build_default_console(tmp_path / "runtime")
    console.project_roots = (tmp_path / "sources",)
    console.handle("oyun geliştirme departmanı kur")

    result = console.handle("BigRepo projesini oyun departmanına bağla")

    assert result.status == "project_linked"
    link = console.projects.require("bigrepo")
    assert link.path == source
    assert (source / "app" / "main.py").exists()
    assert (
        tmp_path / "runtime" / "projects" / "bigrepo" / "INTEGRATION_PLAN.md"
    ).exists()
