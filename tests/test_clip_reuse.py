"""Q7: parça klibi yalnız aynı girdilerle üretildiyse yeniden kullanılır (eski senaryo/ses/varlık/taslak teslime girmez). İki farklı sentetik proje."""
import json
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import clip_cache  # noqa: E402
import render_worker as rw  # noqa: E402
from test_chunked_render import _mk_clip, _runner_factory  # noqa: E402

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg yok")


def project(root, name):
    series = root / name; ep = series / "episodes" / "e1"
    (series / "assets").mkdir(parents=True); (ep / "audio").mkdir(parents=True)
    (series / "assets" / "x.spec.json").write_text('{"height_m": 1.1}', encoding="utf-8")
    (series / "series-bible.json").write_text(json.dumps({"id": name}), encoding="utf-8")
    (series / "locations.json").write_text("{}", encoding="utf-8")
    (ep / "beat_sheet.json").write_text(json.dumps({"beats": [{"t_start": 0, "t_end": 4, "dialogue": "x: " + name}]}), encoding="utf-8")
    (ep / "audio" / "a.wav").write_bytes(b"ses-1")
    (ep / "voice_manifest.json").write_text(json.dumps({"items": [{"beat": 0, "wav": "audio\\a.wav"}]}), encoding="utf-8")
    return series, ep


def go(series, ep, calls, bible=None, runner=None):
    calls.clear()
    out = rw.run_chunked(str(ep), bible or {"id": series.name}, 0, 4, str(series), chunk_s=2, runner=runner or _runner_factory(calls), free_bytes=10**12)
    assert out["status"] == "PASSED", out
    return out


CHANGES = {
    "senaryo": lambda s, e: (e / "beat_sheet.json").write_text('{"beats": []}', encoding="utf-8"),
    "ses_listesi": lambda s, e: (e / "voice_manifest.json").write_text('{"items": []}', encoding="utf-8"),
    "ses_dosyasi": lambda s, e: (e / "audio" / "a.wav").write_bytes(b"ses-2"),
    "varlik_surumu": lambda s, e: (s / "assets" / "x.spec.json").write_text('{"height_m": 1.6}', encoding="utf-8"),
    "yeni_varlik": lambda s, e: (s / "assets" / "y.spec.json").write_text("{}", encoding="utf-8"),
    "mekan": lambda s, e: (s / "locations.json").write_text('{"a": {}}', encoding="utf-8"),
}


@pytest.mark.parametrize("name", ["bir_dizi", "baska_dizi"])
@pytest.mark.parametrize("change", sorted(CHANGES))
def test_changed_input_is_not_served_from_an_old_clip(tmp_path, name, change):
    series, ep = project(tmp_path, name); calls = []
    go(series, ep, calls)
    assert go(series, ep, calls) and calls == []                      # aynı girdi: yeniden üretim yok
    CHANGES[change](series, ep)
    out = go(series, ep, calls)
    assert len(calls) == 2 and all("girdiler değişti" in c["remade_because"] for c in out["chunks"]), out
    assert go(series, ep, calls) and calls == []


def test_bible_fps_engine_source_and_draft_permission_change_the_identity(tmp_path, monkeypatch):
    series, ep = project(tmp_path, "d")

    def fp(**kw):
        a = dict(bible={"id": "d"}, fps=12, engine="2d", t1=2)
        a.update(kw)
        return clip_cache.fingerprint(str(ep), a["bible"], str(series), 0, a["t1"], a["fps"], a["engine"], 16)
    monkeypatch.delenv("AHOS_ALLOW_ESTIMATED_VOICE", raising=False)
    base = fp()
    assert fp() == base
    assert len({base, fp(bible={"id": "d", "v": 2}), fp(fps=24), fp(engine="toon"), fp(t1=3)}) == 5
    monkeypatch.setenv("AHOS_ALLOW_ESTIMATED_VOICE", "1")
    assert fp() != base
    monkeypatch.delenv("AHOS_ALLOW_ESTIMATED_VOICE")
    tools = tmp_path / "motor"; tools.mkdir(); (tools / "m.py").write_text("A = 1\n", encoding="utf-8")
    monkeypatch.setattr(clip_cache, "HERE", str(tools))
    one = fp()
    (tools / "m.py").write_text("A = 2\n", encoding="utf-8")
    assert fp() != one


def test_clip_without_record_or_replaced_clip_is_remade(tmp_path):
    series, ep = project(tmp_path, "d"); calls = []
    go(series, ep, calls)
    first = str(ep / "render" / "clip_0_2.mp4")
    os.remove(clip_cache.record_path(first))                          # kayıtsız (eski sürümden kalan) klip
    _mk_clip(str(ep / "render" / "clip_2_4.mp4"), 2.0)
    with open(ep / "render" / "clip_2_4.mp4", "ab") as f:             # doğru süreli ama başka içerik
        f.write(b"\0" * 16)
    out = go(series, ep, calls)
    assert calls == [(0, 2), (2, 4)]
    assert "kaydı yok" in out["chunks"][0]["remade_because"] and "değişti" in out["chunks"][1]["remade_because"], out


def test_interrupted_remake_does_not_leave_a_trusted_record(tmp_path):
    series, ep = project(tmp_path, "d"); calls = []
    go(series, ep, calls)
    CHANGES["senaryo"](series, ep)
    out = rw.run_chunked(str(ep), {"id": "d"}, 0, 4, str(series), chunk_s=2, runner=_runner_factory([], fail_at=0), free_bytes=10**12)
    assert out["status"] == "BLOCKED"
    assert not os.path.exists(clip_cache.record_path(str(ep / "render" / "clip_0_2.mp4")))


def test_draft_mark_survives_reuse(tmp_path):
    series, ep = project(tmp_path, "d"); calls = []
    inner = _runner_factory(calls)
    assert go(series, ep, calls, runner=lambda *a: dict(inner(*a), draft=True))["draft"] is True
    out = go(series, ep, calls)
    assert calls == [] and out["draft"] is True
