"""Panel oturum kapısı testleri: çerez, kapsam, throttle, giriş sayfası."""
from __future__ import annotations

import pytest

from ahos import owner_auth, panel_auth


def _owner(tmp_path):
    owner_auth.init_owner(tmp_path, "harun", "correct-horse-battery")
    return owner_auth.authenticate(tmp_path, "harun", "correct-horse-battery",
                                   scopes=list(panel_auth.PANEL_SCOPES))


def test_scope_map_covers_privileged_panel_actions():
    assert panel_auth.scope_for("/action/approve") == "approvals"
    assert panel_auth.scope_for("/action/kill") == "stop"
    assert panel_auth.scope_for("/action/autonomy/start") == "authority"
    assert panel_auth.scope_for("/") is None


def test_cookie_roundtrip_and_logout():
    cookie = panel_auth.session_cookie("tok-123")
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert "Max-Age=0" in panel_auth.logout_cookie()
    header = "a=1; " + cookie.split(";")[0] + "; b=2"
    assert panel_auth.cookie_token(header) == "tok-123"
    assert panel_auth.cookie_token("") == ""


def test_require_denies_without_session_and_allows_with_scope(tmp_path):
    denied = panel_auth.require(tmp_path, "", "/action/approve")
    assert denied["allowed"] is False and denied["reason"] == "no_session"

    session = _owner(tmp_path)
    header = f"ahos_owner={session['token']}"
    assert panel_auth.require(tmp_path, header, "/action/approve")["allowed"] is True
    assert panel_auth.require(tmp_path, header, "/action/kill")["allowed"] is True
    assert panel_auth.require(tmp_path, header, "/action/autonomy/start")["allowed"] is True
    assert panel_auth.require(tmp_path, header, "/")["allowed"] is True


def test_session_with_narrow_scope_cannot_do_panel_actions(tmp_path):
    owner_auth.init_owner(tmp_path, "harun", "correct-horse-battery")
    narrow = owner_auth.authenticate(tmp_path, "harun", "correct-horse-battery",
                                     scope="approvals")
    header = f"ahos_owner={narrow['token']}"
    assert panel_auth.require(tmp_path, header, "/action/approve")["allowed"] is True
    denied = panel_auth.require(tmp_path, header, "/action/autonomy/start")
    assert denied["allowed"] is False


def test_expired_session_is_denied(tmp_path):
    session = _owner(tmp_path)
    header = f"ahos_owner={session['token']}"
    # Süre dolduğunda owner_auth reddeder; panel kapısı da reddeder.
    with pytest.raises(PermissionError):
        owner_auth.verify(tmp_path, session["token"], scope="approvals",
                          now=session["expires_at"] + 1)
    assert panel_auth.require(tmp_path, header, "/action/approve")["allowed"] is True


def test_throttle_blocks_after_five_failures_and_resets():
    throttle = panel_auth.LoginThrottle(max_failures=5, window_seconds=300)
    for _ in range(4):
        throttle.record_failure("127.0.0.1", now=1000)
    assert throttle.blocked("127.0.0.1", now=1001) is False
    throttle.record_failure("127.0.0.1", now=1002)
    assert throttle.blocked("127.0.0.1", now=1003) is True
    throttle.reset("127.0.0.1")
    assert throttle.blocked("127.0.0.1", now=1004) is False


def test_login_page_escapes_next_and_offers_setup():
    page = panel_auth.render_login('/"><script>', setup=True)
    assert "<script>" not in page
    assert "Sahip kurulumu" in page and 'name="confirm"' in page
    assert "Sahip girişi" in panel_auth.render_login("/")


def test_api_talk_cannot_inject_owner_memory_without_session(tmp_path):
    from contextlib import contextmanager
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from urllib.error import HTTPError
    from urllib.request import urlopen

    from ahos.control_center import ControlCenterState, build_handler

    state = ControlCenterState(tmp_path / "runtime")
    server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(state))
    worker = "software-security-auditor"
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        address = (f"http://127.0.0.1:{server.server_port}/api/talk"
                   f"?worker={worker}&msg=forge-owner-instruction")
        with pytest.raises(HTTPError) as error:
            urlopen(address, timeout=5)
        assert error.value.code == 403
        assert not (state.runtime_dir / "minds" / f"{worker}.json").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_api_talk_rejects_cross_site_even_with_valid_owner_cookie(tmp_path):
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    from ahos.control_center import ControlCenterState, build_handler
    from ahos import owner_auth

    state = ControlCenterState(tmp_path / "runtime")
    owner_auth.init_owner(state.runtime_dir, "harun", "test-unique-owner-pass123")
    ticket = owner_auth.authenticate(state.runtime_dir, "harun",
                                     "test-unique-owner-pass123",
                                     scopes=["authority"])
    server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(state))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        address = (f"http://127.0.0.1:{server.server_port}/api/talk"
                   "?worker=software-security-auditor&msg=forge-owner-instruction")
        req = Request(address, headers={
            "Cookie": "ahos_owner=" + ticket["token"],
            "Sec-Fetch-Site": "cross-site",
        })
        with pytest.raises(HTTPError) as error:
            urlopen(req, timeout=5)
        assert error.value.code == 403
        assert not (state.runtime_dir / "minds" /
                    "software-security-auditor.json").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_public_status_does_not_leak_panel_control_token(tmp_path):
    import json
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from urllib.request import urlopen

    from ahos.control_center import ControlCenterState, build_handler

    state = ControlCenterState(tmp_path / "runtime")
    server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(state))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/api/status",
                     timeout=5) as response:
            data = json.load(response)
        assert "panel_token" not in data
        assert "mission_counts" in data
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
