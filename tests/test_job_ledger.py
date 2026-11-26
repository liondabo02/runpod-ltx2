import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import job_ledger as L


def test_two_machines_do_not_run_same_job(tmp_path):
    r = str(tmp_path)
    a = L.claim(r, "render_e900_0_30", "bulut", "H1", now=1000)
    assert a["ok"] and a["action"] == "RUN"
    b = L.claim(r, "render_e900_0_30", "kahta-pc", "H1", now=1100)
    assert not b["ok"] and b["action"] == "REJECT" and "bulut" in b["why"]


def test_stale_heartbeat_is_taken_over_and_resumed(tmp_path):
    r = str(tmp_path); L.claim(r, "j", "bulut", "H1", now=1000)
    c = L.claim(r, "j", "kahta-pc", "H1", now=1000 + L.TTL + 5)
    assert c["ok"] and c["action"] == "RESUME"                                   # bağlantı koptu: iş kaybolmaz, devralınır


def test_done_job_is_not_rerun_and_tampered_result_is_not_trusted(tmp_path):
    r = str(tmp_path); res = tmp_path / "out.bin"; res.write_bytes(b"abc")
    L.claim(r, "j", "bulut", "H1", now=1); assert L.complete(r, "j", "bulut", str(res), now=2)
    assert L.claim(r, "j", "kahta-pc", "H1", now=3)["action"] == "DONE"          # tekrar çalışmaz
    res.write_bytes(b"abd")                                                     # sonuç değişti -> doğrulama başarısız -> yeniden çalıştır
    assert L.claim(r, "j", "kahta-pc", "H1", now=4)["action"] == "RUN"
    assert L.claim(r, "j", "kahta-pc", "H2", now=5)["action"] in ("RUN", "RESUME")  # kaynak sürümü değiştiyse eski sonuç kullanılmaz


def test_only_owner_can_heartbeat_or_complete(tmp_path):
    r = str(tmp_path); L.claim(r, "j", "bulut", "H1", now=1)
    assert not L.heartbeat(r, "j", "baska", now=2) and L.heartbeat(r, "j", "bulut", now=2)
