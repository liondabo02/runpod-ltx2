"""Browser presentation contracts for the interactive AHOS 3D office."""
from __future__ import annotations

import shutil
import subprocess

from ahos.office_3d import render_html


def test_3d_office_has_navigation_and_live_status(tmp_path):
    html = render_html()
    for control in ("deptNav", "resetView", "toggleLabels", "inspector", "connection"):
        assert f'id="{control}"' in html
    assert "verified_active_workers" in html
    assert "activity_verified===true" in html
    assert "roomById" in html
    assert "for (let k=0;k<list.length;k++)" in html  # no invisible workers
    assert "renderer.domElement.addEventListener('click',onClick)" in html


def test_3d_office_chat_does_not_inject_untrusted_html(tmp_path):
    html = render_html()
    start = html.index("function chat(list){")
    end = html.index("function fillWho(deps)", start)
    chat = html[start:end]
    assert "innerHTML" not in chat
    assert "textContent" in chat
    assert "replaceChildren" in chat


def test_3d_office_script_syntax(tmp_path):
    html = render_html()
    script = html.split('<script type="module">', 1)[1].split("</script>", 1)[0]
    module = tmp_path / "office3d.mjs"
    module.write_text(script, encoding="utf-8")
    node = shutil.which("node")
    if node:
        run = subprocess.run([node, "--check", str(module)], capture_output=True, text=True)
        assert run.returncode == 0, run.stdout + run.stderr
