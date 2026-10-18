"""Actual loopback HTTP -> owner console -> durable queue, isolated state."""
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import build_opener, ProxyHandler, Request
from urllib.parse import urlencode
from urllib.error import HTTPError
import pytest
from ahos.control_center import ControlCenterState, build_handler


@pytest.fixture
def panel(tmp_path):
    state = ControlCenterState(tmp_path / 'holding')
    server = ThreadingHTTPServer(('127.0.0.1', 0), build_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = 'http://127.0.0.1:' + str(server.server_port)
    opener = build_opener(ProxyHandler({}))
    def request(path, body=None, origin=None, host=None):
        headers = {}
        if origin is not None:headers['Origin'] = origin
        if host is not None:headers['Host'] = host
        req = Request(base + path, data=urlencode(body).encode() if body is not None else None, headers=headers)
        try:
            with opener.open(req, timeout=10) as response:return response.status, response.read()
        except HTTPError as exc:
            with exc:return exc.code, exc.read()
    try:
        yield state, base, request
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


def test_turkish_goal_reaches_durable_department_and_reports_blocked_production(panel):
    state, base, request = panel
    status, body = request('/action/command', {'command': 'çizgi film departmanı kur'}, origin=base)
    assert status == 200
    assert 'Çizgi Film'.encode() in body
    snapshot = json.loads(request('/api/status')[1])
    assert snapshot['missions']
    assert any(m['status'] == 'blocked' for m in snapshot['missions'])
    restarted = ControlCenterState(state.runtime_dir)
    assert restarted.console.book.get('creative') is not None
    assert restarted.console.queue.list()


def test_cross_origin_cannot_submit_goal(panel):
    state, base, request = panel
    before = len(state.console.queue.list())
    assert request('/action/command', {'command': 'çizgi film departmanı kur'}, origin='https://untrusted.invalid')[0] == 403
    assert len(state.console.queue.list()) == before


def test_foreign_host_cannot_submit_goal(panel):
    state, base, request = panel
    assert request('/action/command', {'command': 'çizgi film departmanı kur'}, host='untrusted.invalid')[0] == 403


def test_oversized_command_rejected_before_execution(panel):
    state, base, request = panel
    assert request('/action/command', {'command': 'x' * 17000}, origin=base)[0] == 413
    assert not state.console.queue.list()


def test_reviewed_guidance_reaches_actual_model_prompt(tmp_path):
    from ahos.llm_executor import build_prompt
    root = tmp_path / 'project'
    root.mkdir()
    prompt = build_prompt(root, 'Kaynak kaybını düzelt')
    assert 'Agency Agents' in prompt
    assert 'ölçülebilir kabul' in prompt
    assert 'yürütme izni vermez' in prompt
    assert 'sadece JSON' in prompt
