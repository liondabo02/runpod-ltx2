import os, sys, json, time
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import render2d as r2
from PIL import Image

PLAN = {"fps": 4, "t0": 0.0, "t1": 3.0, "beats": [{"i": 0}]}
DES = {"a": {"height": 1.0}}
_CALLS = {"n": 0}


def fake_frame(plan, designs, t):
    _CALLS["n"] += 1
    return Image.new("RGB", (1280, 720), (int(t * 20) % 255, 80, 120))


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    monkeypatch.setattr(r2, "frame", fake_frame)
    monkeypatch.setenv("AHOS_RENDER_WORKERS", "1")
    _CALLS["n"] = 0


def test_pick_workers_memory_aware(monkeypatch):
    monkeypatch.delenv("AHOS_RENDER_WORKERS", raising=False)
    assert r2.pick_workers(8, mem_mb=1000) == 1            # bellek az: tek işçi
    assert r2.pick_workers(8, mem_mb=1200 + 450 * 3) == 3
    assert r2.pick_workers(2, mem_mb=64000) == 2           # CPU sınırı
    monkeypatch.setenv("AHOS_RENDER_WORKERS", "1")
    assert r2.pick_workers(8, mem_mb=64000) == 1


def test_single_worker_atomic_and_complete(tmp_path):
    r = r2.render_window(PLAN, DES, str(tmp_path))
    assert r["missing"] == 0 and r["rendered"] == 12
    assert not [f for f in os.listdir(tmp_path) if f.endswith(".tmp.png")]
    assert not os.path.exists(tmp_path / ".render.lock")


def test_resume_skips_valid_and_redoes_corrupt(tmp_path):
    r2.render_window(PLAN, DES, str(tmp_path)); first = _CALLS["n"]
    open(tmp_path / "f00003.png", "wb").write(b"\x89PNG broken")          # yarım/bozuk kare
    r = r2.render_window(PLAN, DES, str(tmp_path))
    assert r["rendered"] == 1 and r["missing"] == 0 and _CALLS["n"] == first + 1


def test_stale_cache_quarantined_when_engine_input_changes(tmp_path):
    r2.render_window(PLAN, DES, str(tmp_path))
    r = r2.render_window(PLAN, {"a": {"height": 1.7}}, str(tmp_path))      # tasarım değişti
    assert r["stale_moved"] == 12 and r["rendered"] == 12
    assert any("_stale_" in d for d in os.listdir(tmp_path.parent))


def test_live_lock_blocks_second_job(tmp_path):
    json.dump({"pid": 1, "started": "x", "beat": time.time()}, open(tmp_path / ".render.lock", "w"))
    with pytest.raises(RuntimeError):
        r2.render_window(PLAN, DES, str(tmp_path))
    assert not [f for f in os.listdir(tmp_path) if f.endswith(".png")]
    assert os.path.exists(tmp_path / ".render.lock")                       # başkasının kilidine dokunulmadı


def test_stale_lock_taken_over(tmp_path):
    json.dump({"pid": 1, "started": "x", "beat": time.time() - 5000}, open(tmp_path / ".render.lock", "w"))
    assert r2.render_window(PLAN, DES, str(tmp_path))["missing"] == 0


def test_cancel_file_stops(tmp_path):
    open(tmp_path / ".cancel", "w").write("1")
    r = r2.render_window(PLAN, DES, str(tmp_path))
    assert r["cancelled"] and r["rendered"] == 0


def _flaky(args):
    raise MemoryError("sim")


def test_worker_crash_falls_back_to_fewer_workers(tmp_path, monkeypatch):
    monkeypatch.setenv("AHOS_RENDER_WORKERS", "2")
    monkeypatch.setattr(r2, "_work", _flaky)
    # işçi çökünce yedek yol: önce 2 -> 1; tek işçi yolunda da flaky olduğu için sonunda eksik kalır ve rapor eder
    r = r2.render_window(PLAN, DES, str(tmp_path), frame_timeout=20)
    assert r["retries"] >= 1 and r["workers_end"] == 1 and r["missing"] == 12
