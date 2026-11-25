import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import voice_licence as L

def test_nc_voices_blocked_in_commercial_mode(monkeypatch):
    monkeypatch.delenv("AHOS_COMMERCIAL", raising=False)
    for e in ("mms_tts", "piper_tr_dfki", "xtts_v2"):
        ok, msg = L.check(e); assert not ok and "KAPALI" in msg, e

def test_nc_voices_allowed_only_when_explicitly_non_commercial(monkeypatch):
    monkeypatch.setenv("AHOS_COMMERCIAL", "0"); assert L.check("mms_tts")[0]

def test_unverified_warns_but_is_not_called_permitted(monkeypatch):
    monkeypatch.delenv("AHOS_COMMERCIAL", raising=False)
    ok, msg = L.check("edge_tts"); assert ok and "DOĞRULANMADI" in msg
    ok, msg = L.check("bilinmeyen_motor"); assert ok and "DOĞRULANMADI" in msg

def test_kurmanci_tts_is_blocked_by_localisation_worker(monkeypatch, tmp_path):
    src = open(os.path.join(os.path.dirname(__file__), "..", "tools", "localisation_worker.py"), encoding="utf-8").read()
    assert 'voice_licence.check("mms_tts")' in src            # kmr (MMS) ticari teslimde ses üretmez
