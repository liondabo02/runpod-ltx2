# -*- coding: utf-8 -*-
"""Sahibin onayladığı senaryo verisinden (s01e001_data) beat_sheet üretir. LLM YOK: senaryo olduğu gibi (replikler, süreler,
kamera, mekân, karakterler) taşınır; hiçbir şey eklenmez/uydurulmaz. Çıktı: showrunner --beats-file ile kullanılır."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import s01e001_data as D  # noqa: E402


def _loc_id(env_id):
    return env_id.replace("env_", "").replace("_v1", "")[:30]


def _emotion(action, lines):
    t = (action + " " + " ".join(lines)).lower()
    arousal = 0.35 + 0.15 * t.count("!") + (0.2 if re.search(r"koş|zıpl|uç|fırla|hop|hızl", t) else 0)
    valence = 0.7 if re.search(r"gül|sarıl|mutlu|güzel|bayram|alkış|harika", t) else (0.35 if re.search(r"üzül|ağla|korku|kayıp|ıslak", t) else 0.55)
    return {"valence": round(min(1, valence), 2), "arousal": round(min(1, arousal), 2), "intensity": round(min(1, (arousal + 0.3) / 1.3), 2)}


def build(series_title="Merhaba, Bizim Aile! — Parkın Kuralları"):
    beats, cur = [], 0.0
    for sc in D.SCENES:
        loc = _loc_id(D.LOCATIONS[sc["loc"]]["id"])
        for i, sh in enumerate(sc["shots"]):
            dur, size, motion, chars, start, end, action, lines, trans = sh
            chars = list(chars); dlg = []; extra_sound = []
            for ln in lines:
                who, _, txt = ln.partition(":")
                who = who.strip(); txt = txt.strip()
                if who not in chars: chars.append(who)
                if txt.startswith("["):
                    extra_sound.append(txt.strip("[]"))      # bebek sesi: konuşma değil, ses efekti
                else:
                    dlg.append(f"{who}: {txt}")
            baby = any(c in D.BABIES for c in chars)
            beats.append({
                "t_start": cur, "t_end": cur + dur, "scene_id": sc["id"].upper(), "location": loc,
                "light_time": sc["light"], "characters": chars,
                "action": f"{action}. ({start} -> {end})",
                "dialogue": " | ".join(dlg), "emotion": _emotion(action, lines),
                "camera": f"{size}, {motion}",
                "sound": "; ".join(["ortam sesi", f"geçiş: {trans}"] + extra_sound),
                "safety_note": "bebek yetişkin gözetiminde; ip, küçük parça ya da yalnız bırakma yok" if baby else "",
                "shot_id": f"{sc['id']}_sh{i + 1:02d}"})
            cur += dur
    return {"schema": "ahos.beat_sheet.v1", "status": "FROM_OWNER_SCRIPT", "series_id": "ahos-bizim-aile",
            "title": series_title, "logline": "Aden ve Kaan'ın ailesi parkta park kurallarını öğrenir.", "total_seconds": cur, "beats": beats}


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(HERE), "studio", "s01e001-parkin-kurallari", "beat_sheet_from_script.json")
    s = build(); json.dump(s, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(s["beats"]), "vuruş", s["total_seconds"], "sn ->", out)
