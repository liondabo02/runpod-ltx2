from __future__ import annotations

from pathlib import Path

from ahos.llm_executor import build_prompt


def _project(tmp_path: Path) -> Path:
    (tmp_path / "www").mkdir(parents=True)
    (tmp_path / "www" / "card-keys.js").write_text(
        "// kart tuslari\nwindow.x = 1;\n", encoding="utf-8"
    )
    (tmp_path / "www" / "index.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"name":"x"}', encoding="utf-8")
    return tmp_path


def test_file_task_uses_small_focused_prompt(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("AHOS_LLM_FOCUSED", raising=False)
    root = _project(tmp_path)

    prompt = build_prompt(root, "card-keys.js dosyasına yorum ekle")

    assert "card-keys.js" in prompt
    assert "window.x = 1;" in prompt
    assert "package.json" not in prompt  # envanter gönderilmiyor
    assert len(prompt) < 6000


def test_focused_prompt_can_be_disabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AHOS_LLM_FOCUSED", "0")
    root = _project(tmp_path)

    prompt = build_prompt(root, "card-keys.js dosyasına yorum ekle")

    assert "package.json" in prompt or "Proje kökü" in prompt


def test_task_without_file_keeps_full_prompt(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("AHOS_LLM_FOCUSED", raising=False)
    root = _project(tmp_path)

    prompt = build_prompt(root, "oyunu daha eglenceli yap")

    assert "Proje kökü" in prompt
