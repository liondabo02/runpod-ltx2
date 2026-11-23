# -*- coding: utf-8 -*-
"""'Bizim Aile' dizisi için bible + 2D spec dosyalarını kanondan (s01e001_data) deterministik üretir. Yeni karakter tasarlamaz:
renkler/aksesuarlar onaylı poster kıyafet açıklamalarından alınır. Çıktı: series/<id>/series-bible.json + assets/<id>.spec.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import s01e001_data as D  # noqa: E402

SERIES_ID = "ahos-bizim-aile"
# id: (ad, yaş, kadın?, boy m, saç stili, aksesuar, palet)
LOOK = {
 "aden": ("Aden", 3, True, 0.98, "ponytail", "star", dict(hair="#462D1E", skin="#F5CDAA", shirt="#286EC8", shorts="#1E2F6E", accent="#FFD23C")),
 "kaan": ("Kaan", 1, False, 0.76, "short", "none", dict(hair="#19191E", skin="#E8BE96", shirt="#DC5A46", shorts="#3C3C5A", accent="#F3E7D3")),
 "esra": ("Esra", 33, True, 1.62, "hijab", "none", dict(hair="#5A3A28", skin="#F1CBA6", shirt="#F3E4C8", shorts="#8A6A58", accent="#B9606A", scarf="#B9606A")),
 "ahmet": ("Ahmet", 33, False, 1.76, "short", "none", dict(hair="#2A1E18", skin="#EBC29C", shirt="#7A2430", shorts="#25304A", accent="#243A66")),
 "esma": ("Esma", 29, True, 1.64, "hijab", "none", dict(hair="#5A3A28", skin="#F4D0AE", shirt="#EAE0C4", shorts="#8D8F62", accent="#7C8F5A", scarf="#7C8F5A")),
 "harun": ("Harun", 30, False, 1.90, "ponytail", "none", dict(hair="#2B1C14", skin="#E6B98F", shirt="#26365E", shorts="#2D2A36", accent="#D9C9A8")),
 "veysel": ("Veysel", 33, False, 1.74, "short", "none", dict(hair="#B88A52", skin="#F0C8A4", shirt="#2F7C80", shorts="#4E3A28", accent="#8A5A2B")),
 "oznur": ("Öznur", 31, True, 1.62, "hijab", "none", dict(hair="#4A2E28", skin="#EDC7A2", shirt="#6E8ED0", shorts="#6E2C48", accent="#7A3A8C", scarf="#7A3A8C")),
 "salih": ("Salih", 2, False, 0.86, "short", "none", dict(hair="#B5622C", skin="#EDBF98", shirt="#D9A53A", shorts="#4F7A4A", accent="#6B4A2E")),
 "medine": ("Medine", 0, True, 0.50, "short", "bow", dict(hair="#6A3D24", skin="#F7D8C0", shirt="#F5C8D2", shorts="#F5C8D2", accent="#F29BB0")),
 "davut": ("Davut", 30, False, 1.80, "ponytail", "none", dict(hair="#3A2418", skin="#E4B792", shirt="#B03030", shorts="#4A2F22", accent="#5C3A28")),
 "fatos": ("Fatoş", 30, True, 1.66, "bob", "none", dict(hair="#6A3E2C", skin="#E9C3A0", shirt="#EAD9C8", shorts="#E0836C", accent="#E0836C")),
 "emos": ("Emoş", 4, True, 1.02, "bob", "bow", dict(hair="#6A3E2C", skin="#F2CBA8", shirt="#2FA7A0", shorts="#E8735A", accent="#D83A3A")),
 "berzan": ("Berzan", 2, False, 0.88, "short", "none", dict(hair="#15100E", skin="#D9A57C", shirt="#E8782A", shorts="#222E58", accent="#F2C14B")),
 "aras": ("Aras", 2, False, 0.88, "short", "none", dict(hair="#2E1E16", skin="#F0C8A4", shirt="#3A6FC0", shorts="#222E58", accent="#D9C9A8")),
 "ramin": ("Ramin", 0, False, 0.46, "short", "none", dict(hair="#2A1C14", skin="#E3B590", shirt="#BFE3D0", shorts="#BFE3D0", accent="#8FC9B0")),
}
ROLE = {"aden": "kız çocuk, ana rol", "kaan": "erkek bebek, ana rol", "esra": "anne", "ahmet": "baba", "esma": "teyze, hamile", "harun": "enişte, lider",
        "veysel": "aile dostu", "oznur": "aile dostu anne", "salih": "oğlan çocuk", "medine": "kız bebek", "davut": "aile dostu, iri", "fatos": "aile dostu anne",
        "emos": "kız çocuk", "berzan": "oğlan çocuk, ikiz", "aras": "oğlan çocuk, ikiz", "ramin": "erkek bebek"}

# canon farklılaştırma önerilerinden (studio/s01e001-parkin-kurallari/character_differentiation_proposals.json) gelen yüz/vücut ayrıntıları
EXTRA = {
 "aden": dict(freckles=3, eye_scale=1.05, eye_shape="round", nose="button", brow_shape="soft", mouth_w=1.15),
 "kaan": dict(face_w=1.0, eye_scale=1.1, eye_shape="wide", nose="button", mouth_w=1.2, blush=0.8, brow_shape="arched", freckles=True),
 "esra": dict(face_w=1.06, build=1.08, lowerwear="pants", eye_shape="almond", lashes=True, brow_shape="arched", nose="line", blush=0.55, mouth_w=0.95),
 "ahmet": dict(build=0.9, eyebags=True, eye_color=[0.12, 0.08, 0.06], lowerwear="pants", eye_shape="narrow", brow_shape="thick", nose="round", beard="short", face_w=1.06, blush=0.2, mouth_w=1.0),
 "esma": dict(face_w=0.94, lashes=True, pregnant=True, lowerwear="skirt", eye_shape="round", brow_shape="soft", nose="button", blush=0.7, mouth_w=0.9),
 "harun": dict(beard="short", build=0.95, lowerwear="pants", eye_shape="almond", brow_shape="arched", nose="long", blush=0.15, mouth_w=1.1, eye_dist=1.05),
 "veysel": dict(beard="stubble", build=1.12, eye_color=[0.2, 0.45, 0.8], lowerwear="pants", eye_shape="round", brow_shape="thick", nose="round", blush=0.3, mouth_w=1.2),
 "oznur": dict(face_w=0.9, lowerwear="pants", brow_w=0.8, eye_shape="wide", lashes=True, brow_shape="flat", nose="button", freckles=True, blush=0.6, mouth_w=0.85),
 "salih": dict(face_w=1.06, eye_shape="round", nose="button", mouth_w=1.1, freckles=True, brow_shape="thick"),
 "medine": dict(lashes=True, face_w=1.0, eye_scale=1.05, eye_shape="sleepy", nose="button", mouth_w=0.6, blush=0.9, brow_shape="arched"),
 "davut": dict(build=1.3, face_w=1.16, lowerwear="pants", eye_shape="sleepy", eye_scale=0.9, brow_shape="soft", nose="long", beard="full", blush=0.4, mouth_w=1.3),
 "fatos": dict(earrings=True, face_w=1.12, lowerwear="pants", eye_shape="sleepy", lid=0.3, eyebags=True, brow_shape="soft", nose="line", blush=0.25, mouth_w=0.85),
 "emos": dict(eye_shape="wide", nose="dot", mouth_w=1.2, brow_shape="soft"),
 "berzan": dict(dimple=True, face_w=0.94, eye_shape="wide", nose="round", mouth_w=1.3, brow_shape="arched", eye_scale=1.08),
 "aras": dict(face_w=0.96, eye_shape="narrow", nose="line", mouth_w=0.8, brow_shape="flat", eyebags=True),
 "ramin": dict(face_w=1.14, eye_scale=1.2, eye_shape="round", nose="dot", mouth_w=0.9, blush=1.6),
}
HAIR_STYLE = {"aden": "wavy_long", "harun": "wavy_long", "davut": "curly", "salih": "curly", "berzan": "bangs", "emos": "bangs", "aras": "short"}
ACC = {"ramin": "beanie", "oznur": "flower_pin"}

# kalıcı ses kimliği (edge-tts tr-TR iki ses + perde/hız): aynı cinsiyetteki karakterler birbirinden belirgin ayrışsın
VOICE_ID = {"aden": (32, 6), "kaan": (52, -4), "esra": (0, -2), "ahmet": (-4, 0), "esma": (9, -8), "harun": (-14, -6), "veysel": (7, 3),
            "oznur": (15, 4), "salih": (46, 4), "medine": (60, -10), "davut": (-24, -9), "fatos": (-7, 2), "emos": (42, 10),
            "berzan": (36, 9), "aras": (30, -4), "ramin": (62, -12)}


def _rgb01(h):
    h = h.lstrip("#"); return [round(int(h[i:i + 2], 16) / 255.0, 4) for i in (0, 2, 4)]


def build(root=None):
    root = root or ROOT; sdir = os.path.join(root, "series", SERIES_ID); adir = os.path.join(sdir, "assets"); os.makedirs(adir, exist_ok=True)
    chars = []
    for cid in D.ORDER:
        name, age, fem, h, style, acc, pal = LOOK[cid]
        chars.append({"id": cid, "name": name, "age": age, "role": ROLE[cid] + (" (kadın)" if fem and "kız" not in ROLE[cid] else ""), "look": D.WARDROBE[cid],
                      "personality": "", "safety_notes": ["bebek: konuşma yok"] if cid in D.BABIES else [],
                      "identity_lock": {"reference_png": f"studio/reference/owner_accepted_roster_v1/characters/{D.ORDER.index(cid)+1:02d}_{cid if cid!='oznur' else 'oznur'}.png", "sha256": "", "model_hash": "", "rig_hash": ""},
                      "voice": {"pitch_hz": VOICE_ID[cid][0], "rate_pct": VOICE_ID[cid][1], "profile_id": cid, "hint": ("bebek mırıltısı" if cid in D.BABIES else ""), "engine": "edge-tts", "licence_status": "review_required"}})
        json.dump({"species": "human", "hair_style": HAIR_STYLE.get(cid, style), "accessory": ACC.get(cid, acc), **EXTRA.get(cid, {}), "palette": {k: _rgb01(v) for k, v in pal.items()}, "height_m": h,
                   "class": "infant" if age < 2 else None}, open(os.path.join(adir, cid + ".spec.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    locs = [{"id": v["id"].replace("env_", "").replace("_v1", "")[:30], "name": v["name"], "description": v["notes"]} for v in D.LOCATIONS.values()]
    bible = {"schema": "ahos.series_bible.v1", "series_id": SERIES_ID, "title": "Merhaba, Bizim Aile!", "language_default": "tr", "age_band": "2-5",
             "tone": "sıcak, eğlenceli, öğretici", "visual_style": {"look": "yumuşak sıcak renkler", "frame_rate": 24, "render_style": "2d_flat_puppet_12fps"},
             "characters": chars, "locations": locs, "continuity": {"episodes": [], "running_facts": []},
             "episode_defaults": {"min_seconds": 480, "max_cost_eur": 1.0}, "owner_approval": {"identity": "PENDING", "episode_final": "PENDING"}}
    json.dump(bible, open(os.path.join(sdir, "series-bible.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return bible


if __name__ == "__main__":
    b = build(); print(len(b["characters"]), "karakter", len(b["locations"]), "mekân ->", SERIES_ID)
