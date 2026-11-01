from __future__ import annotations

from ahos.self_repair import (
    MAX_ATTEMPTS,
    error_excerpt,
    feedback_prompt,
    plan_attempts,
    should_retry,
)


def test_error_excerpt_prefers_error_lines() -> None:
    output = "genel bilgi\nsözdizimi hatası: card-keys.js:12\nbaşka satır\n1 sorun bulundu"

    excerpt = error_excerpt(output)

    assert "sözdizimi hatası" in excerpt
    assert "1 sorun bulundu" in excerpt


def test_error_excerpt_handles_empty() -> None:
    assert error_excerpt("") == "(çıktı yok)"


def test_feedback_prompt_contains_error_and_schema_rule() -> None:
    prompt = feedback_prompt("TEMEL", "sözdizimi hatası: a.js")

    assert "TEMEL" in prompt
    assert "sözdizimi hatası" in prompt
    assert "en küçük yama" in prompt


def test_feedback_prompt_includes_file_content() -> None:
    prompt = feedback_prompt("TEMEL", "hata", {"www/a.js": "const x = 1;\n"})

    assert "www/a.js" in prompt
    assert "const x = 1;" in prompt


def test_should_retry_until_max() -> None:
    assert should_retry(1) is True
    assert should_retry(MAX_ATTEMPTS) is False


def test_plan_attempts_default() -> None:
    extra, reason = plan_attempts("sözdizimi hatası")

    assert extra == MAX_ATTEMPTS - 1
    assert "geri beslenebilir" in reason


def test_plan_attempts_permission_blocks_retry() -> None:
    extra, reason = plan_attempts("Permission denied: /etc/passwd")

    assert extra == 0
    assert "yetki" in reason


def test_plan_attempts_empty_output() -> None:
    extra, reason = plan_attempts("")

    assert extra == 0
    assert "boş" in reason
