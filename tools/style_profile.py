# -*- coding: utf-8 -*-
"""Dizi/film bazlı üslup profili: her referans türü aynı hareket/efekt setini kullanmaz.
Seçim: ortam değişkeni AHOS_STYLE=<ön ayar adı> veya series/<id>/style_profile.json ({"preset": "...", "override": {...}}).
Alanlar: energy (hareket/jest genliği çarpanı), gait (yürüyüş kişilikleri), speak_acting (nefes+vurgu jesti), dust (ayak tozu/hız çizgisi),
decor (iç mekân yaşam izleri), park_decor (dış mekân yaşam izleri), cut_s (hedef ortalama çekim sn)."""
import json, os

PRESETS = {
    "komedi_aile": dict(energy=1.0, gait=True, speak_acting=True, dust=True, decor=True, park_decor=True, cut_s=3.5),   # Caillou/Scooby arası: canlı ama ev sıcaklığı
    "macera":      dict(energy=1.3, gait=True, speak_acting=True, dust=True, decor=True, park_decor=True, cut_s=2.8),   # Scooby/Şirinler: hızlı kurgu, koşu, tepki
    "slapstick":   dict(energy=1.6, gait=True, speak_acting=True, dust=True, decor=True, park_decor=True, cut_s=2.2),   # Tom & Jerry: abartı, hız
    "masal":       dict(energy=0.7, gait=False, speak_acting=True, dust=False, decor=True, park_decor=False, cut_s=4.5), # masal anlatımı: sakin jest, yavaş kurgu
    "sakin_egitim": dict(energy=0.6, gait=False, speak_acting=True, dust=False, decor=True, park_decor=True, cut_s=5.0),
}
DEFAULT = "komedi_aile"


def load(series_dir=None):
    name = os.environ.get("AHOS_STYLE", "").strip()
    over = {}
    if not name and series_dir:
        p = os.path.join(series_dir, "style_profile.json")
        if os.path.exists(p):
            try:
                j = json.load(open(p, encoding="utf-8")); name = j.get("preset", ""); over = j.get("override", {})
            except Exception:
                pass
    prof = dict(PRESETS.get(name or DEFAULT, PRESETS[DEFAULT])); prof.update(over); prof["preset"] = name or DEFAULT
    return prof


def current():
    return load(os.environ.get("AHOS_SERIES_DIR"))
