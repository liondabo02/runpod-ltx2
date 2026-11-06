from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from ahos.adapters.ruflo import RufloConfig, make_ruflo_executor
from ahos.worker_runtime import WorkItem


@pytest.fixture(autouse=True)
def _allow_execute_mode(monkeypatch):
    # Testler yürütme mekaniğini ölçer; ücret politikası ayrı testte sınanır.
    monkeypatch.setenv("AHOS_ALLOW_PAID_LLM", "1")


def _item() -> WorkItem:
    return WorkItem(
        task_id="m-1:produce",
        title="kart dosyasına yorum ekle",
        department="oyun",
        required_capabilities=frozenset({"code"}),
    )


def _fake_cli(tmp_path: Path, body: str) -> Path:
    cli = tmp_path / "fake_ruflo.py"
    cli.write_text(body, encoding="utf-8")
    return cli


def _executor(tmp_path: Path, cli: Path, timeout: float = 30):
    return make_ruflo_executor(
        tmp_path / "proj",
        tmp_path / "artifacts",
        config=RufloConfig(
            node=sys.executable,
            cli=str(cli),
            timeout_seconds=timeout,
            command_template="{node} {cli}",
        ),
    )


def _gate(project: Path, *, ok: bool = True) -> None:
    tools = project / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    (tools / "check_offline.py").write_text(
        "print('kapı temiz')\nraise SystemExit(0)\n"
        if ok
        else "print('kapı başarısız')\nraise SystemExit(1)\n",
        encoding="utf-8",
    )


def test_ruflo_change_is_reported_as_delivery(tmp_path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "a.js").write_text("// eski\n", encoding="utf-8")
    _gate(project, ok=True)
    cli = _fake_cli(
        tmp_path,
        "from pathlib import Path\n"
        "Path('a.js').write_text('// yeni\\n', encoding='utf-8')\n"
        "print('ruflo ok')\n",
    )

    result = _executor(tmp_path, cli)(_item(), "engineer-1")

    assert result.success is True
    assert "bağımsız kabul geçti" in result.summary
    assert (project / "a.js").read_text(encoding="utf-8") == "// yeni\n"
    assert result.artifacts and Path(result.artifacts[0]).exists()


def test_failing_acceptance_blocks_delivery(tmp_path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "a.js").write_text("// eski\n", encoding="utf-8")
    _gate(project, ok=False)
    cli = _fake_cli(
        tmp_path,
        "from pathlib import Path\n"
        "Path('a.js').write_text('// yeni\\n', encoding='utf-8')\n",
    )

    result = _executor(tmp_path, cli)(_item(), "engineer-1")

    assert result.success is False
    assert "bağımsız kabul BAŞARISIZ" in result.summary


def test_missing_acceptance_gate_blocks_delivery(tmp_path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    cli = _fake_cli(
        tmp_path,
        "from pathlib import Path\nPath('a.js').write_text('x', encoding='utf-8')\n",
    )

    result = _executor(tmp_path, cli)(_item(), "engineer-1")

    assert result.success is False
    assert "kabul" in result.summary.lower()


def test_no_change_is_not_a_delivery(tmp_path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    cli = _fake_cli(tmp_path, "print('hiçbir şey yapmadım')\n")

    result = _executor(tmp_path, cli)(_item(), "engineer-1")

    assert result.success is False
    assert "dosya değişmedi" in result.summary


def test_timeout_kills_and_reports(tmp_path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    cli = _fake_cli(tmp_path, "import time\ntime.sleep(30)\n")

    result = _executor(tmp_path, cli, timeout=1)(_item(), "engineer-1")

    assert result.success is False
    assert "zaman aşımı" in result.summary


def test_exit_code_failure_is_reported(tmp_path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    cli = _fake_cli(tmp_path, "raise SystemExit(3)\n")

    result = _executor(tmp_path, cli)(_item(), "engineer-1")

    assert result.success is False
    assert "hata kodu 3" in result.summary


def test_child_env_has_no_paid_keys(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-paid")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-paid")
    project = tmp_path / "proj"
    project.mkdir()
    cli = _fake_cli(
        tmp_path,
        "import json, os\n"
        "print(json.dumps({k: v for k, v in os.environ.items() if 'API_KEY' in k}))\n"
        "open('env.json','w').write(str({k: v for k, v in os.environ.items() if 'API_KEY' in k}))\n",
    )

    _executor(tmp_path, cli)(_item(), "engineer-1")

    leaked = json.loads((project / "env.json").read_text(encoding="utf-8").replace("'", '"'))
    assert leaked == {}
