"""Dil başına yerel ses motoru seçimi (Piper). Varsayılan edge-tts'tir; yerel ses yalnız AHOS_TTS=piper iken denenir.
Seçim kuralları (hiçbiri sessizce geçilmez; sonuç rapora yazılır):
  - dilin languages.json'da 'piper' girdisi yoksa -> edge-tts (başka dilin sesiyle OKUTULMAZ)
  - ses lisansı ticari teslimde kapalıysa (voice_licence.check) -> edge-tts + neden
  - model dosyası (.onnx ve .onnx.json) yoksa -> edge-tts + neden
Piper paketi GPL-3.0'dır: bu repo onu içe aktarmaz, yalnız `python -m piper` ayrı süreç olarak çağırır."""
import os

import voice_licence

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def model_dir():
    return os.environ.get("AHOS_PIPER_DIR") or os.path.join(ROOT, "models", "piper")


def enabled(env=None):
    return (env or os.environ).get("AHOS_TTS", "edge").lower() == "piper"


def resolve(code, lang_info):
    """-> {"engine": "piper"|"edge-tts", "model": yol|None, "licence_key": ..., "note": str}"""
    edge = {"engine": "edge-tts", "model": None, "licence_key": "edge_tts", "note": ""}
    if not enabled():
        return edge
    cfg = (lang_info or {}).get("piper")
    if not cfg:
        edge["note"] = "dil '%s' için yerel Piper sesi tanımlı değil; edge-tts kullanıldı" % code
        return edge
    key = cfg.get("licence_key") or voice_licence.PIPER_MODEL_KEYS.get(cfg.get("model", ""), "piper_" + str(cfg.get("model")))
    ok, msg = voice_licence.check(key)
    if not ok:
        edge["note"] = "Piper sesi kullanılamadı: " + msg + "; edge-tts kullanıldı"
        return edge
    base = os.path.join(model_dir(), cfg["model"])
    if not (os.path.isfile(base + ".onnx") and os.path.isfile(base + ".onnx.json")):
        edge["note"] = "Piper model dosyası yok (%s); edge-tts kullanıldı" % (cfg["model"] + ".onnx[.json]")
        return edge
    return {"engine": "piper", "model": base + ".onnx", "licence_key": key, "note": msg}


def engine_info(res):
    """voice_worker.run(engine=...) için manifest alanları."""
    if res["engine"] != "piper":
        return None            # None -> voice_worker varsayılan edge-tts bilgisini yazar
    r = voice_licence.REGISTRY.get(res["licence_key"], {})
    com = r.get("commercial", "unverified")
    return {"engine": "piper:" + os.path.basename(res["model"]).replace(".onnx", ""),
            "licence_status": "card_cc0_verified" if com == "yes" else "review_required",
            "licence_note": (r.get("voice_data", "?") + " | " + r.get("source", "")) + (" | " + res["note"] if res["note"] else "")}
