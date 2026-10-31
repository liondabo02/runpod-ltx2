"""The staged hotfix removes the direct completion path without touching live code."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest


def _safe_text():
    file = Path(__file__).resolve().parents[2] / "tools" / "prepare_doc_hotfix.py"
    return runpy.run_path(str(file))["safe_daemon_text"]


def test_direct_sql_document_completion_removed_without_touching_drain():
    safe_text = _safe_text()
    before = (
        "        # BELGE YOLU: proje bağlı olmayan departmanların bekleyen görevleri\n"
        "        # model/QA zincirine girmeden gerçek dosyaya dönüştürülür.\n"
        "        # preface\n"
        '        sql = "update missions set status=\'completed\' where mission_id=?"\n'
        "\n"
        "        # SÜREKLİ ÖĞRENME: boştaki çalışanlar\n"
        "        route_through_owner_console()\n"
    )
    after = safe_text(before)
    assert "update missions set status='completed'" not in after
    assert "route_through_owner_console()" in after
    assert "independent QA" in after


def test_unexpected_source_layout_is_never_silently_rewritten():
    with pytest.raises(ValueError, match="markers"):
        _safe_text()("a totally different daemon source")
