"""One-off: render the last missions inside the office page."""

from __future__ import annotations

from pathlib import Path

PATH = (
    Path(__file__).resolve().parents[2]
    / "ahos_core"
    / "ahos"
    / "office_server.py"
)

CSS = """
#recentWrap{padding:8px 18px;border-bottom:1px solid var(--line);font-size:12px;color:var(--muted)}
#recentWrap b{color:var(--ink)}
.recentItem{display:inline-block;margin-right:14px;white-space:nowrap}
.ok{color:var(--ok)}.bad{color:var(--bad)}
"""

BODY = """<div id="recentWrap">son görevler: <span id="recent">-</span></div>
"""

JS = """    const recent = d.holding.recent || [];
    document.getElementById('recent').innerHTML = recent.slice(0,5).map(function(m){
      const cls = m.changed > 0 ? 'ok' : 'bad';
      return '<span class="recentItem"><b>'+m.at+'</b> <span class="'+cls+'">'+m.status+
        '</span> '+m.changed+' dosya · '+m.objective.slice(0,42)+'</span>';
    }).join('') || '<span class="bad">henüz görev yok</span>';
"""


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    if "recentWrap" in text:
        print("zaten var")
        return 0
    text = text.replace("#ceoBox{position:fixed", CSS + "#ceoBox{position:fixed", 1)
    text = text.replace("<main id=\"rooms\"></main>", BODY + "<main id=\"rooms\"></main>", 1)
    text = text.replace(
        "    const rooms = document.getElementById('rooms'); rooms.innerHTML='';",
        JS + "    const rooms = document.getElementById('rooms'); rooms.innerHTML='';",
        1,
    )
    PATH.write_text(text, encoding="utf-8")
    print("son görevler arayüze eklendi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
