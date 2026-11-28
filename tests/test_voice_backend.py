"""V12 (c) arka uç: ayrı süreç. pyworld bulutta yoksa WORLD ölçüsü ATLANIR (sahte geçiş yok); PC'de ayrı ortamda koşar."""
import json, os, subprocess, sys
import numpy as np
import pytest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import voice_backend as vb
import voice_identity as vi

SR = 16000


def test_kaynak_ses_yoksa_model_yuklemeden_durur(tmp_path):
    jobs = tmp_path / "j.json"; jobs.write_text(json.dumps([{"text": "x", "lang": "tr", "out": str(tmp_path / "o.wav")}]))
    rep = tmp_path / "r.json"
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "voice_backend.py"), "--jobs", str(jobs), "--ref", str(tmp_path / "yok.wav"), "--report", str(rep)])
    assert p.returncode == 2 and json.load(open(rep))["status"] == "KAYNAK_SES_YOK"


def _harm(f0, secs=1.0):
    t = np.arange(int(secs * SR)) / SR
    return sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 10)) * 0.2


@pytest.mark.skipif(__import__("importlib").util.find_spec("pyworld") is None, reason="pyworld bu ortamda yok (PC ses ortamında koşar)")
@pytest.mark.parametrize("st,fr", [(7.0, 1.0), (0.0, 1.3), (12.0, 1.4)])
def test_world_perde_ve_formant_bagimsiz(st, fr):
    x = _harm(120.0)
    y = vb.world_transform(x, SR, {"pitch_st": st, "formant_ratio": fr})
    f = vi.median_f0(y, SR)
    assert abs(12 * np.log2(f / 120.0) - st) < 1.0       # perde yalnız pitch_st kadar kayar (formant oranından bağımsız)
    assert abs(len(y) - len(x)) < 0.05 * len(x)
