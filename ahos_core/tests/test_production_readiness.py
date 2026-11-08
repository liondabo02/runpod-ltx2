"""Üretime hazırlık kabul testleri (kriter 4, 5, 6).

- Kriter 5: yedek al → veriyi boz → geri yükle → veri kaybı yok.
- Kriter 6: güvenlik sınırları (yasak dizin/uzantı, yetki seviyeleri).
- Kriter 4: hatalı ajanı durdurma ve yeniden atama (devre kesici).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from ahos import agent_control
from ahos.agent_hooks import pre_edit
from ahos.governance import ActionRequest, AuthorityLevel, GovernancePolicy


def _queue(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.execute(
        "create table if not exists missions (mission_id text primary key, status text, objective text)"
    )
    con.commit()
    return con


def test_backup_and_restore_keeps_every_row(tmp_path: Path) -> None:
    """Kriter 5: yedekten geri yükleme veri kaybı olmadan çalışır."""

    db = tmp_path / "company-service.db"
    con = _queue(db)
    con.executemany(
        "insert into missions values (?,?,?)",
        [(f"CMD-{i}", "completed", f"görev {i}") for i in range(25)],
    )
    con.commit()
    before = con.execute("select count(*) from missions").fetchone()[0]
    con.close()

    backup = tmp_path / "backup.db"
    with sqlite3.connect(db) as source, sqlite3.connect(backup) as target:
        source.backup(target)

    # veri kaybı simülasyonu: tablo silinir
    with sqlite3.connect(db) as con:
        con.execute("delete from missions")
        con.commit()
        assert con.execute("select count(*) from missions").fetchone()[0] == 0

    with sqlite3.connect(backup) as source, sqlite3.connect(db) as target:
        source.backup(target)

    with sqlite3.connect(db) as con:
        after = con.execute("select count(*) from missions").fetchone()[0]
        objectives = [row[0] for row in con.execute("select objective from missions")]

    assert after == before == 25
    assert "görev 7" in objectives


def test_security_blocks_forbidden_directory(tmp_path: Path) -> None:
    """Kriter 6: üretilen kopya dizinlere yazma engellenir."""

    (tmp_path / "android" / "app").mkdir(parents=True)
    (tmp_path / "android" / "app" / "x.js").write_text("a", encoding="utf-8")

    result = pre_edit("android/app/x.js", root=tmp_path)

    assert result.allowed is False
    assert "kopya" in result.detail


def test_security_blocks_unknown_extension(tmp_path: Path) -> None:
    """Kriter 6: izin verilmeyen uzantı reddedilir."""

    (tmp_path / "kur.exe").write_bytes(b"x")

    result = pre_edit("kur.exe", root=tmp_path)

    assert result.allowed is False


def test_security_requires_authority_for_destructive_action() -> None:
    """Kriter 6: yıkıcı/dağıtım eylemleri sahip onayı ister."""

    policy = GovernancePolicy()
    request = ActionRequest(
        name="deploy_to_production",
        authority=AuthorityLevel.D,
        destructive=True,
    )
    decision = policy.evaluate(request)

    assert decision.allowed is False or decision.owner_approval_required is True


def test_breaker_stops_faulty_agent_and_can_be_reassigned(tmp_path: Path) -> None:
    """Kriter 4: hatalı ajan durdurulur; sıfırlanınca yeniden atanabilir."""

    for _ in range(4):
        decision = agent_control.breaker(tmp_path, "oyun-engineering-specialist", success=False)

    assert decision.action == "stop"

    agent_control.reset_breaker(tmp_path, "oyun-engineering-specialist")
    fresh = agent_control.breaker(tmp_path, "oyun-engineering-specialist")

    assert fresh.action == "ok"


def test_breaker_steers_before_constraining(tmp_path: Path) -> None:
    """Kriter 4: merdiven sırası korunur (steer → constrain → stop)."""

    first = agent_control.breaker(tmp_path, "w", success=False)
    second = agent_control.breaker(tmp_path, "w", success=False)
    third = agent_control.breaker(tmp_path, "w", success=False)
    fourth = agent_control.breaker(tmp_path, "w", success=False)

    assert (first.action, second.action, third.action, fourth.action) == (
        "ok",
        "steer",
        "constrain",
        "stop",
    )
