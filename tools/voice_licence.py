"""Ses motoru/ses verisi lisans kaydı ve ticari teslim koruması. DOĞRULANMAMIŞ ≠ izinli: 'unverified' uyarı verir, 'no' engeller.
Kaynaklar (2026-11-25): HF model kartları/depo sayfaları; kod/ağırlık/ses verisi AYRI satırlar."""
import os

REGISTRY = {
    "mms_tts": {"code": "MIT/Apache (transformers)", "weights": "CC-BY-NC 4.0", "voice_data": "CC-BY-NC 4.0", "commercial": "no",
                "source": "facebook/mms-tts-* model kartı; kurmancî (kmr) bu sesi kullanıyor"},
    "piper_tr_dfki": {"code": "MIT (piper)", "weights": "MIT etiketli (rhasspy/piper-voices)", "voice_data": "CC BY-NC-SA 4.0 (DFKI Türkçe veri)", "commercial": "no",
                      "source": "rhasspy/piper-voices tr_TR/dfki MODEL_CARD → github.com/marytts/dfki-ot-data"},
    "piper_tr_fahrettin": {"code": "MIT (piper)", "weights": "?", "voice_data": "?", "commercial": "unverified", "source": "MODEL_CARD alınamadı"},
    "piper_tr_fettah": {"code": "MIT (piper)", "weights": "?", "voice_data": "?", "commercial": "unverified", "source": "MODEL_CARD alınamadı"},
    "edge_tts": {"code": "MIT (edge-tts istemcisi)", "weights": "Microsoft bulut servisi (model yok)", "voice_data": "Microsoft", "commercial": "unverified",
                 "source": "Microsoft hizmet şartları; sahip kararı bekliyor (review_required)"},
    "xtts_v2": {"code": "MPL", "weights": "CPML", "voice_data": "kullanıcı referansı", "commercial": "no", "source": "Coqui CPML"},
    "freya_tts_small": {"code": "Apache-2.0", "weights": "Apache-2.0 (HF kartı)", "voice_data": "kartta belirtilmedi", "commercial": "unverified",
                        "source": "huggingface.co/freyavoice/freya-tts; tek konuşmacı, klonlama yok; eğitim verisi lisansı doğrulanmadı"},
    "f5_tts_turkish_karayakar": {"code": "?", "weights": "MIT etiketli", "voice_data": "?", "commercial": "unverified", "source": "yalnız ikincil kaynak"},
    "omnivoice": {"code": "Apache-2.0 (k2-fsa/OmniVoice)", "weights": "belirtilmedi", "voice_data": "belirtilmedi", "commercial": "unverified",
                  "source": "github.com/k2-fsa/OmniVoice; Türkçe desteği doğrulanmadı; yetkisiz klonlama yasak"},
}

def commercial_mode():
    return os.environ.get("AHOS_COMMERCIAL", "1") != "0"        # varsayılan: ticari teslim (NC sesler engelli)

def check(engine):
    """(izin_var_mı, mesaj). Kayıtta yoksa 'unverified' sayılır."""
    r = REGISTRY.get(engine, {"commercial": "unverified", "source": "kayıt yok"})
    if r["commercial"] == "no" and commercial_mode():
        return False, f"{engine}: ticari kullanıma KAPALI ({r.get('voice_data')}); ticari teslimde kullanılamaz"
    if r["commercial"] == "unverified":
        return True, f"{engine}: ticari kullanım DOĞRULANMADI ({r['source']}); teslimden önce doğrulanmalı"
    return True, ""
