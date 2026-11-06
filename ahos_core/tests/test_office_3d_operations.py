"""Acceptance contracts for the upgraded, read-only 3D headquarters."""
from __future__ import annotations

import shutil
import subprocess

import pytest

from ahos.office_3d import render_html


@pytest.fixture
def html():
    return render_html()


def test_office_has_ceo_map_search_and_scene_preset_controls(html):
    for node in ("focusCEO", "topView", "officeSearch", "miniMap",
                 "opsBoard", "opsEvents", "collapseBoard", "lowPower",
                 "reduceMotion", "workerDetail"):
        assert f'id="{node}"' in html
    assert "focusDepartment('holding')" in html
    assert "function searchOffice(query)" in html
    assert "function drawMiniMap(snapshot)" in html
    assert "function chooseMiniMapPoint(x,y)" in html


def test_office_uses_only_real_observed_activity_not_fake_labor(html):
    assert "verified_active_workers" in html
    assert "w.activity_verified===true" in html
    assert "worker.activity_verified===true" in html
    assert "ceoWorkers.some(w=>w.activity_verified===true)" in html
    assert "beacon.material.color.setHex(verified?0x59e8b6:0x7996b8)" in html
    assert "kanıt yok" in html


def test_activity_board_and_worker_details_do_not_render_untrusted_html(html):
    start=html.index("function updateOperations(snapshot){")
    end=html.index("function searchOffice(query){",start)
    panel=html[start:end]
    assert "replaceChildren" in panel
    assert "textContent" in panel
    assert "innerHTML" not in panel
    start=html.index("function inspectDepartment(id,")
    end=html.index("function focusDepartment(id,",start)
    inspector=html[start:end]
    assert "textContent" in inspector
    assert "innerHTML" not in inspector


def test_scene_has_no_misleading_ceo_busy_flag_and_no_background_render(html):
    assert "makeRoom(0, ceoZ, 320, 230, 0xffd166, true" not in html
    assert "ceoWorkers.some(w=>w.activity_verified===true)" in html
    assert "if(document.hidden)return;" in html
    assert "if(!reducedMotion)for(const a of avatars)" in html
    assert "renderer.setPixelRatio(lowPowerMode?1:" in html


def test_map_and_search_are_keyboard_accessible(html):
    assert 'id="miniMap" width="280" height="122" tabindex="0"' in html
    assert "officeMap.addEventListener('keydown'" in html
    assert "officeMap.addEventListener('click'" in html
    assert "searchBox.addEventListener('keydown'" in html
    assert "e.key==='Enter'" in html
    assert "e.key==='Escape'" in html
    assert "aria-pressed" in html


def test_chat_rejects_unauthorized_api_response_without_erasing_message(html):
    start=html.index("async function talk(){")
    end=html.index("async function loadRenders()",start)
    talk=html[start:end]
    assert "if(!r.ok)" in talk
    assert "r.status===403" in talk
    assert "msg.value='';" in talk
    assert talk.index("if(!r.ok)") < talk.index("msg.value='';")


def test_live_office_module_passes_node_syntax_check(html,tmp_path):
    node=shutil.which("node")
    if not node:
        pytest.skip("node not available")
    source=html.split('<script type="module">',1)[1].split("</script>",1)[0]
    target=tmp_path/"hq3d.mjs"
    target.write_text(source,encoding="utf-8")
    result=subprocess.run([node,"--check",str(target)],
                          capture_output=True,text=True,timeout=15)
    assert result.returncode==0, result.stdout+result.stderr
