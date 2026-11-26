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


def test_real_worker_death_is_survived_and_reported(tmp_path, monkeypatch):
    """Gerçek süreç ölümü (os._exit): havuz bozulur, işçi sayısı düşer, tek işçide kareler tamamlanır."""
    monkeypatch.setenv("AHOS_RENDER_WORKERS", "2")
    monkeypatch.setenv("AHOS_TEST_FAULT", "crash")
    r = r2.render_window(PLAN, DES, str(tmp_path), frame_timeout=30)
    assert r["retries"] >= 1 and r["workers_end"] == 1


def test_real_hang_times_out_and_does_not_hang_forever(tmp_path, monkeypatch):
    monkeypatch.setenv("AHOS_RENDER_WORKERS", "2")
    monkeypatch.setenv("AHOS_TEST_FAULT", "hang")
    t0 = time.time()
    r = r2.render_window(PLAN, DES, str(tmp_path), frame_timeout=2)
    assert r["timeouts"] >= 1 and r["retries"] >= 1
    assert time.time() - t0 < 50                      # takılan işçi sonsuza dek beklenmedi



def test_hidden_object_disappears_after_reaching_target(monkeypatch):
    """Regresyon: şişe çöp kutusuna atıldıktan sonra kutu ağzında/Harun'un önünde asılı kalıyordu."""
    calls = []
    monkeypatch.setattr(r2.props2d, "draw", lambda *a, **k: calls.append(a))
    beat = {"targets": {"bin_green": (1.3, 0.9)}, "choreo": {"objects": [{"prop": "bottle", "track": [{"t": 0, "at": [0.0, 0.0]}, {"t": 2.0, "at": "bin_green", "hide": True}]}]}}
    r2._draw_objects(None, None, beat, [], {}, 1.0)
    assert len(calls) == 1                         # uçuş sırasında görünür
    calls.clear(); r2._draw_objects(None, None, beat, [], {}, 2.5)
    assert calls == []                             # vardıktan sonra yok


def test_head_crop_check_includes_hair_and_bottom_edge():
    class Cam:
        s = 250.0
        def x(self, v): return 640 + v * 250.0
        def y(self, v): return 700 - v * 250.0 * 1.6      # yakın plan ölçeği
    assert r2._head_cropped(Cam(), 3.5, 1.7) is False      # tamamen dışarıda: sorun değil
    assert r2._head_cropped(Cam(), 0.0, 2.0) is True       # başı üstten kesilen uzun boylu karakter


def test_reaction_shot_goes_to_listener():
    beat = {"cast": ["a", "b"], "lines": [{"char": "a", "start": 0.0, "end": 4.0}, {"char": "b", "start": 6.0, "end": 7.0}]}
    assert r2.reaction_target(beat, 1.0) is None                 # replik başı: konuşana
    assert r2.reaction_target(beat, 0.62 * 4.0 + 0.1) == "b"     # uzun replikin ortasında dinleyene (b) kes
    assert r2.reaction_target(beat, 4.3) == "b"                  # a bitti, kimse konuşmuyor → dinleyen b
    assert r2.reaction_target(beat, 6.5) is None                 # b konuşuyor
    assert r2.reaction_target({"cast": ["a"], "lines": beat["lines"]}, 4.3) is None   # tek karakter: tepki yok


def test_render_does_not_start_when_disk_is_insufficient(tmp_path, monkeypatch):
    import shutil, collections
    DU = collections.namedtuple("du", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda p: DU(100e9, 100e9 - 50e6, 50e6))      # 50 MB boş
    r = r2.render_window(PLAN, DES, str(tmp_path))
    assert r["disk_blocked"] and r["missing"] == 12 and r["rendered"] == 0
    assert not [f for f in os.listdir(tmp_path) if f.endswith(".png")]                  # hiçbir kare yazılmadı


def test_render_starts_when_disk_is_sufficient(tmp_path, monkeypatch):
    r = r2.render_window(PLAN, DES, str(tmp_path))
    assert not r.get("disk_blocked") and r["missing"] == 0 and r["disk_need_mb"] > 0


def test_render_worker_blocks_invalid_object_track(tmp_path):
    import json, render_worker as rw
    ep = tmp_path / "ep"; ep.mkdir()
    bad = {"beats": [{"id": "b1", "t_start": 0, "t_end": 5, "characters": ["a"], "choreo": {"objects": [{"prop": "bottle", "track": [{"t": 0, "holder": "a"}, {"t": 3, "at": [1.7, 0.7], "hide": True}]}]}}]}
    json.dump(bad, open(ep / "beat_sheet.json", "w"))
    r = rw.run(str(ep), {"characters": []}, 0, 5, str(tmp_path))
    assert r["status"] == "BLOCKED" and r["error"] == "NESNE_IZI_GECERSIZ" and "imha" in r["problems"][0]
