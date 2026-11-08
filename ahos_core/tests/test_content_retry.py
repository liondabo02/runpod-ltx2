from __future__ import annotations

import json
from pathlib import Path

from ahos.llm_executor import (
    ModelSettings,
    _content_mode_retry,
)
from ahos.worker_runtime import WorkItem


def _settings() -> ModelSettings:
    return ModelSettings(
        base_url="http://127.0.0.1:11500/v1",
        api_key="local-only",
        model="qwen2.5-coder:7b",
        max_usd_per_run=0.0,
        input_usd_per_1k=0.0,
        output_usd_per_1k=0.0,
        timeout_seconds=60,
        max_files=2,
        max_bytes=12000,
        max_tokens=800,
    )


def _item() -> WorkItem:
    return WorkItem(
        task_id="m-1:produce",
        title="card-keys.js dosyasına yorum ekle",
        department="oyun",
        required_capabilities=frozenset({"code"}),
    )


def _project(tmp_path: Path) -> Path:
    (tmp_path / "www").mkdir(parents=True)
    (tmp_path / "www" / "card-keys.js").write_text("// eski\n", encoding="utf-8")
    return tmp_path


def test_content_retry_returns_full_file_edit(tmp_path) -> None:
    root = _project(tmp_path)
    answer = json.dumps(
        {
            "summary": "yorum eklendi",
            "risk": "low",
            "edits": [
                {
                    "path": "www/card-keys.js",
                    "content": "// eski\n// ahos-yorum\n",
                }
            ],
        }
    )

    parsed = _content_mode_retry(
        lambda system, user, settings: answer, _settings(), root, _item(), "card-keys.js dosyasına yorum ekle"
    )

    assert parsed is not None
    assert parsed.edits[0].path == "www/card-keys.js"


def test_content_retry_skips_unchanged_content(tmp_path) -> None:
    root = _project(tmp_path)
    answer = json.dumps(
        {
            "summary": "değişmedi",
            "risk": "low",
            "edits": [{"path": "www/card-keys.js", "content": "// eski\n"}],
        }
    )

    parsed = _content_mode_retry(
        lambda system, user, settings: answer, _settings(), root, _item(), "card-keys.js dosyasına yorum ekle"
    )

    assert parsed is None


def test_content_retry_skips_large_files(tmp_path) -> None:
    root = _project(tmp_path)
    (root / "www" / "card-keys.js").write_text("x" * 5000, encoding="utf-8")

    parsed = _content_mode_retry(
        lambda system, user, settings: "{}", _settings(), root, _item(), "card-keys.js"
    )

    assert parsed is None
