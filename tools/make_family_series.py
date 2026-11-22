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
 "salih": ("Salih", 2, False, 0.86, "short", "none", dict(hair="#A8643C", skin="#F2CBA8", shirt="#D9A53A", shorts="#4F7A4A", accent="#6B4A2E")),
 "medine": ("Medine", 0, True, 0.50, "short", "bow", dict(hair="#3A2A22", skin="#F2CFB4", shirt="#F5C8D2", shorts="#F5C8D2", accent="#F29BB0")),
 "davut": ("Davut", 30, False, 1.80, "ponytail", "none", dict(hair="#3A2418", skin="#E4B792", shirt="#B03030", shorts="#4A2F22", accent="#5C3A28")),
 "fatos": ("Fatoş", 30, True, 1.66, "bob", "none", dict(hair="#6A3E2C", skin="#E9C3A0", shirt="#EAD9C8", shorts="#E0836C", accent="#E0836C")),
 "emos": ("Emoş", 4, True, 1.02, "bob", "bow", dict(hair="#6A3E2C", skin="#F2CBA8", shirt="#2FA7A0", shorts="#E8735A", accent="#D83A3A")),
 "berzan": ("Berzan", 2, False, 0.88, "short", "none", dict(hair="#2E1E16", skin="#F0C8A4", shirt="#E8782A", shorts="#222E58", accent="#F2C14B")),
 "aras": ("Aras", 2, False, 0.88, "short", "none", dict(hair="#2E1E16", skin="#F0C8A4", shirt="#3A6FC0", shorts="#222E58", accent="#D9C9A8")),
 "ramin": ("Ramin", 0, False, 0.46, "short", "none", dict(hair="#3A2A22", skin="#F2CFB4", shirt="#BFE3D0", shorts="#BFE3D0", accent="#8FC9B0")),
}
ROLE = {"aden": "kız çocuk, ana rol", "kaan": "erkek bebek, ana rol", "esra": "anne", "ahmet": "baba", "esma": "teyze, hamile", "harun": "enişte, lider",
        "veysel": "aile dostu", "oznur": "aile dostu anne", "salih": "oğlan çocuk", "medine": "kız bebek", "davut": "aile dostu, iri", "fatos": "aile dostu anne",
        "emos": "kız çocuk", "berzan": "oğlan çocuk, ikiz", "aras": "oğlan çocuk, ikiz", "ramin": "erkek bebek"}


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
                      "voice": {"profile_id": cid, "hint": ("bebek mırıltısı" if cid in D.BABIES else ""), "engine": "edge-tts", "licence_status": "review_required"}})
        json.dump({"species": "human", "hair_style": style, "accessory": acc, "palette": {k: _rgb01(v) for k, v in pal.items()}, "height_m": h,
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
