"""V12 iskelet: tek kaynak sesten yaş/cinsiyete göre sabit karakter ses ayarı + kaba önizleme dönüştürücü (sahibin sesi olmadan, sentetik)."""
import os, sys
import numpy as np
import pytest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import voice_identity as vi

SR = 16000
SRC_F0 = 120.0   # sentetik yetişkin erkek kaynak


def card(i, age, gender=None, **style):
    c = {"id": i, "age": age, "voice": {}}
    if gender: c["gender"] = gender
    if style: c["voice"]["style"] = style
    return c


def harmonic(f0, secs=1.0):
    t = np.arange(int(secs * SR)) / SR
    return sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 8)) * 0.2


def test_ayni_kart_ayni_ayar_bolumler_arasi_sabit():
    a = vi.derive(card("x", 33, "female"), SRC_F0)["params"]
    b = vi.derive(card("x", 33, "female"), SRC_F0)["params"]
    assert a == b


@pytest.mark.parametrize("young,old", [(3, 33), (1, 9), (12, 30)])
def test_kucuk_yas_daha_yuksek_perde_ve_kisa_ses_yolu(young, old):
    y = vi.derive(card("y", young, "female"), SRC_F0)["params"]
    o = vi.derive(card("o", old, "female"), SRC_F0)["params"]
    assert y["pitch_st"] > o["pitch_st"] and y["formant_ratio"] > o["formant_ratio"]


def test_yetiskin_kadin_erkekten_yuksek():
    f = vi.derive(card("f", 30, "female"), SRC_F0)["params"]; m = vi.derive(card("m", 30, "male"), SRC_F0)["params"]
    assert f["pitch_st"] > m["pitch_st"] + 6 and f["formant_ratio"] > m["formant_ratio"]


def test_yasli_titreme_alir():
    assert vi.derive(card("n", 72, "female"), SRC_F0)["params"]["tremolo"] > 0


def test_cinsiyet_tahmin_edilmez_yetiskinde_sorun_doner():
    r = vi.derive(card("z", 33), SRC_F0)
    assert any("CINSIYET_EKSIK" in p for p in r["problems"]) and r["params"]["gender"] is None


def test_kucuk_cocukta_cinsiyet_zorunlu_degil():
    assert vi.derive(card("c", 3), SRC_F0)["problems"] == []


def test_yas_yoksa_ayar_yok():
    r = vi.derive({"id": "q"}, SRC_F0)
    assert r["params"] is None and "YAS_EKSIK" in r["problems"][0]


def test_stil_sinir_disi_reddedilir():
    r = vi.derive(card("s", 30, "male", pitch_st=9), SRC_F0)
    assert any("STIL_SINIR_DISI" in p for p in r["problems"])


def test_ayirt_edilebilirlik_bilerek_bozma_ayni_kimlik():
    r = vi.identities([card("a", 30, "male"), card("b", 30, "male")], SRC_F0)
    assert any("SESLER_AYIRT_EDILEMIYOR" in p for p in r["problems"])


def test_ayirt_edilebilirlik_stil_ile_cozulur_ve_farkli_sahnede_sorun_yok():
    r = vi.identities([card("a", 30, "male"), card("b", 30, "male", pitch_st=3)], SRC_F0)
    assert not any("AYIRT" in p for p in r["problems"])
    r2 = vi.identities([card("a", 30, "male"), card("b", 30, "male")], SRC_F0, scenes=[["a"], ["b"]])
    assert not any("AYIRT" in p for p in r2["problems"])


def test_motor_kodunda_dil_sozcugu_yok():
    src = open(os.path.join(ROOT, "tools", "voice_identity.py"), encoding="utf-8").read()
    assert '"kadın"' not in src and '"erkek"' not in src


def test_olcu_sentetik_kaynakta_perde_dogru():
    assert abs(vi.median_f0(harmonic(SRC_F0), SR) - SRC_F0) < 6


@pytest.mark.parametrize("age,gender", [(3, None), (30, "female"), (72, "male")])
def test_onizleme_perdeyi_hedefe_tasir_sureyi_korur(age, gender):
    p = vi.derive(card("t", age, gender), SRC_F0)["params"]
    x = harmonic(SRC_F0, 1.0)
    y = vi.transform_preview(x, SR, p)
    assert abs(len(y) - len(x)) <= int(0.02 * len(x))
    f = vi.median_f0(y, SR)
    assert f is not None and abs(12 * np.log2(f / SRC_F0) - p["pitch_st"]) < 1.0, (f, p)


def test_bilerek_bozma_sifir_kaydirma_perdeyi_degistirmez():
    y = vi.transform_preview(harmonic(SRC_F0), SR, {"pitch_st": 0.0, "formant_ratio": 1.0})
    assert abs(vi.median_f0(y, SR) - SRC_F0) < 6
