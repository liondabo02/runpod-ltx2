"""Meta MMS-TTS ile yerel konuşma sentezi (Kurmancî gibi edge-tts'te olmayan diller için).
Gerekli: pip install torch transformers scipy (CPU yeter). Model ilk kullanımda indirilir (~150 MB).
LİSANS: facebook/mms-tts-* modelleri CC-BY-NC 4.0 (ticari değil) — ticari yayın öncesi sahip kararı gerekir."""
import os, wave

_CACHE = {}


def available():
    try:
        import torch, transformers  # noqa: F401
        return True
    except Exception:
        return False


def synth(text, model_id, out_wav, target_sr=16000):
    import torch
    from transformers import VitsModel, AutoTokenizer
    if model_id not in _CACHE:
        _CACHE[model_id] = (VitsModel.from_pretrained(model_id), AutoTokenizer.from_pretrained(model_id))
    model, tok = _CACHE[model_id]
    torch.manual_seed(7)                               # model rastgele; sabit tohum = tekrarlanabilir ses
    with torch.no_grad():
        wav = model(**tok(text, return_tensors="pt")).waveform[0].numpy()
    sr = int(model.config.sampling_rate)
    import numpy as np
    x = np.clip(wav, -1, 1)
    if sr != target_sr:                                # basit yeniden örnekleme (doğrusal)
        n = int(len(x) * target_sr / sr)
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
    os.makedirs(os.path.dirname(os.path.abspath(out_wav)), exist_ok=True)
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(target_sr)
        w.writeframes((x * 32000).astype("<i2").tobytes())
    return len(x) / float(target_sr)
