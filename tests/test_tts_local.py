"""Yerel ses (Piper) seçimi: dil başına doğru model, lisans koruması, sessiz geçiş yok. Gerçek model/ağ gerekmez (sahte dosyalar)."""
import json, os, sys, types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import tts_local as TL  # noqa: E402
import voice_licence as VL  # noqa: E402
import voice_worker as vw  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANGS = json.load(open(os.path.join(ROOT, "studio", "pipeline", "languages.json"), encoding="utf-8"))["languages"]


@pytest.fixture
def models(tmp_path, monkeypatch):
    for m in ("de_DE-thorsten-medium", "es_ES-davefx-medium", "fr_FR-siwis-medium", "tr_TR-dfki-medium"):
        (tmp_path / (m + ".onnx")).write_bytes(b"x"); (tmp_path / (m + ".onnx.json")).write_text("{}")
    monkeypatch.setenv("AHOS_PIPER_DIR", str(tmp_path))
    monkeypatch.delenv("AHOS_COMMERCIAL", raising=False)
    return tmp_path


def test_default_is_edge_even_if_models_exist(models, monkeypatch):
    monkeypatch.delenv("AHOS_TTS", raising=False)
    assert TL.resolve("de", LANGS["de"])["engine"] == "edge-tts"


def test_each_language_gets_its_own_model_never_another_languages(models, monkeypatch):
    monkeypatch.setenv("AHOS_TTS", "piper")
    for code, prefix in (("de", "de_DE"), ("es", "es_ES"), ("fr", "fr_FR")):
        r = TL.resolve(code, LANGS[code])
        assert r["engine"] == "piper" and os.path.basename(r["model"]).startswith(prefix), (code, r)


def test_language_without_piper_entry_falls_back_with_reason_not_to_turkish_voice(models, monkeypatch):
    monkeypatch.setenv("AHOS_TTS", "piper")
    r = TL.resolve("ar", LANGS["ar"])
    assert r["engine"] == "edge-tts" and "ar" in r["note"] and r["model"] is None


def test_noncommercial_voice_is_refused_in_commercial_mode_and_reason_is_reported(models, monkeypatch):
    monkeypatch.setenv("AHOS_TTS", "piper")
    info = {"piper": {"model": "tr_TR-dfki-medium", "licence_key": "piper_tr_dfki"}}
    r = TL.resolve("tr", info)
    assert r["engine"] == "edge-tts" and "KAPALI" in r["note"]
    monkeypatch.setenv("AHOS_COMMERCIAL", "0")
    assert TL.resolve("tr", info)["engine"] == "piper"       # yalnız açıkça ticari-olmayan kipte


def test_missing_model_file_falls_back_and_says_so(models, monkeypatch):
    monkeypatch.setenv("AHOS_TTS", "piper")
    os.remove(models / "de_DE-thorsten-medium.onnx.json")
    r = TL.resolve("de", LANGS["de"])
    assert r["engine"] == "edge-tts" and "model dosyası yok" in r["note"]


def test_tts_piper_refuses_noncommercial_model_before_running_anything(models, monkeypatch, tmp_path):
    called = []
    monkeypatch.setattr(vw.subprocess, "run", lambda *a, **k: called.append(a))
    with pytest.raises(RuntimeError, match="KAPALI"):
        vw.tts_piper("merhaba", "v", "+0%", "+0Hz", str(tmp_path / "o.wav"), model=str(models / "tr_TR-dfki-medium.onnx"))
    assert not called


def test_tts_piper_passes_the_requested_model_to_piper(models, monkeypatch, tmp_path):
    calls = []

    def fake_run(args, **k):
        calls.append(list(args))
        if "piper" in args:                                    # sahte Piper: geçerli bir WAV yaz
            import wave
            with wave.open(args[args.index("-f") + 1], "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050); w.writeframes(b"\0\0" * 2205)
        return types.SimpleNamespace(returncode=0)
    monkeypatch.setattr(vw.subprocess, "run", fake_run)
    m = str(models / "de_DE-thorsten-medium.onnx")
    vw.tts_piper("Hallo Welt", "v", "+0%", "+0Hz", str(tmp_path / "o.wav"), model=m)
    piper_call = [c for c in calls if "piper" in c][0]
    assert piper_call[piper_call.index("-m", piper_call.index("piper") + 1) + 1] == m and "dfki" not in " ".join(piper_call)


def test_manifest_licence_status_is_not_overstated(models, monkeypatch):
    monkeypatch.setenv("AHOS_TTS", "piper")
    de = TL.engine_info(TL.resolve("de", LANGS["de"]))
    fr = TL.engine_info(TL.resolve("fr", LANGS["fr"]))
    assert de["licence_status"] == "card_cc0_verified"
    assert fr["licence_status"] == "review_required"          # lessac zinciri doğrulanmadı: 'doğrulandı' denemez
    assert TL.engine_info(TL.resolve("ar", LANGS["ar"])) is None


def test_every_configured_piper_model_has_a_registry_entry_in_the_right_language():
    for code, info in LANGS.items():
        cfg = info.get("piper")
        if not cfg:
            continue
        assert cfg["model"].split("_")[0] == code, (code, cfg)
        assert VL.PIPER_MODEL_KEYS[cfg["model"]] == cfg["licence_key"] and cfg["licence_key"] in VL.REGISTRY


def test_registry_states_gpl_for_piper_code_not_mit():
    for k, r in VL.REGISTRY.items():
        if k.startswith("piper_"):
            assert "GPL" in r["code"] and "MIT" not in r["code"], k
