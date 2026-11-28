"""Q4: diyalog kapsama kapısı. İki farklı sentetik proje; bilerek eklenen hatalar (eksik/eski replik, yanlış konuşan, yanlış dil, eksik/bozuk/kesik ses, sığmayan replik)."""
import json
import os
import struct
import sys
import wave

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import dialogue_check as dc  # noqa: E402
import render_worker  # noqa: E402
import voice_worker as vw  # noqa: E402
from test_listener_reaction import PROJECTS, make_project  # noqa: E402

DUR = 8.0


def project(tmp_path, name, lang="tr"):
    make_project(tmp_path, name, ["a"])
    root = tmp_path / name
    a, b = PROJECTS[name][0][0], PROJECTS[name][1][0]
    sheet = {"beats": [
        {"t_start": 0, "t_end": DUR, "characters": [a, b], "camera": "geniş", "location": "yer", "action": "Konuşurlar.", "dialogue": f"{a}: Bak şuna! | {b}: Hemen geliyorum."},
        {"t_start": DUR, "t_end": 2 * DUR, "characters": [a, b], "camera": "geniş", "location": "yer", "action": "Bekler.", "dialogue": ""},
        {"t_start": 2 * DUR, "t_end": 3 * DUR, "characters": [a, b], "camera": "geniş", "location": "yer", "action": "Konuşur.", "dialogue": f"{a}: Aferin sana!"}]}
    ep = root / "ep"
    (ep / "beat_sheet.json").write_text(json.dumps(sheet, ensure_ascii=False), encoding="utf-8")
    os.remove(ep / "voice_manifest.json")
    bible = {"id": name, "language_default": lang, "characters": [{"id": c, "name": c.title(), "role": r, "age": g} for c, r, g, _h in PROJECTS[name]]}
    return root, ep, sheet, bible, a, b


def real_manifest(ep, bible, lang="tr"):
    """Gerçek ses dosyalı liste (ses işçisinin biçimi): wav + sha256 + süre."""
    sheet = json.loads((ep / "beat_sheet.json").read_text(encoding="utf-8"))
    (ep / "audio").mkdir(exist_ok=True)
    items = []
    lines, _u, _a = dc.expected_lines(sheet, bible)
    for bi in sorted(lines):
        for li, (c, text) in enumerate(lines[bi]):
            path = ep / "audio" / f"b{bi}_{li}_{c}.wav"
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
                w.writeframes(struct.pack("<%dh" % 16000, *([900, -900] * 8000)))
            items.append({"beat": bi, "char": c, "text": text, "voice": "tr-TR-AhmetNeural", "wav": f"audio/{path.name}",
                          "sha256": vw.sha(str(path)), "duration_s": 1.0})
    return {"status": "PASSED", "lang": lang, "items": items}


def put(ep, man):
    (ep / "voice_manifest.json").write_text(json.dumps(man, ensure_ascii=False), encoding="utf-8")


def rules(ep, bible, **kw):
    return sorted({p["rule"] for p in dc.check(str(ep), bible, **kw)["problems"]})


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_complete_voice_list_passes(tmp_path, name):
    _root, ep, _sheet, bible, _a, _b = project(tmp_path, name)
    put(ep, real_manifest(ep, bible))
    rep = dc.check(str(ep), bible)
    assert rep["problems"] == [] and rep["expected"] == rep["matched"] == 3 and rep["voice"] == "files", rep


def _drop(m, ep, a, b):
    m["items"].pop(1)


def _stale_text(m, ep, a, b):
    m["items"][0]["text"] = "Eski senaryodaki cümle."


def _wrong_speaker(m, ep, a, b):
    m["items"][0]["char"] = b


def _duplicate(m, ep, a, b):
    m["items"].append(dict(m["items"][2]))


def _wrong_language_list(m, ep, a, b):
    m["lang"] = "de"


def _wrong_language_voice(m, ep, a, b):
    m["items"][1]["voice"] = "de-DE-KatjaNeural"


def _missing_file(m, ep, a, b):
    os.remove(ep / m["items"][0]["wav"])


def _changed_file(m, ep, a, b):
    with open(ep / m["items"][0]["wav"], "r+b") as f:
        f.seek(200); f.write(b"\x00" * 40)


def _truncated_file(m, ep, a, b):
    path = ep / m["items"][0]["wav"]
    path.write_bytes(path.read_bytes()[:9000])
    m["items"][0].pop("sha256")


def _short_audio(m, ep, a, b):
    m["items"][0]["duration_s"] = 2.4


def _too_long_for_beat(m, ep, a, b):
    m["items"][2]["duration_s"] = DUR + 0.5


@pytest.mark.parametrize("name", sorted(PROJECTS))
@pytest.mark.parametrize("break_it,expected", [
    (_drop, {"REPLIK_EKSIK"}), (_stale_text, {"REPLIK_EKSIK", "REPLIK_FAZLA"}), (_wrong_speaker, {"REPLIK_EKSIK", "REPLIK_FAZLA"}),
    (_duplicate, {"REPLIK_FAZLA"}), (_wrong_language_list, {"YANLIS_DIL_SESI"}), (_wrong_language_voice, {"YANLIS_DIL_SESI"}),
    (_missing_file, {"SES_DOSYASI_YOK"}), (_changed_file, {"SES_DOSYASI_DEGISMIS"}), (_truncated_file, {"SES_DOSYASI_BOZUK"}),
    (_short_audio, {"SES_SURESI_UYUSMUYOR"}), (_too_long_for_beat, {"REPLIK_SIGMIYOR", "SES_SURESI_UYUSMUYOR"})])
def test_injected_dialogue_fault_is_caught_by_name(tmp_path, name, break_it, expected):
    _root, ep, _sheet, bible, a, b = project(tmp_path, name)
    man = real_manifest(ep, bible)
    break_it(man, ep, a, b)
    put(ep, man)
    assert set(rules(ep, bible)) == expected


def test_missing_list_corrupt_list_and_window(tmp_path):
    _root, ep, _sheet, bible, _a, _b = project(tmp_path, "kisa_uzun")
    assert rules(ep, bible) == ["SES_LISTESI_YOK"]
    assert rules(ep, bible, t0=DUR, t1=2 * DUR) == []                        # repliksiz pencere ses istemez
    (ep / "voice_manifest.json").write_text("{yarım", encoding="utf-8")
    assert rules(ep, bible) == ["SES_LISTESI_BOZUK"]
    man = real_manifest(ep, bible)
    man["items"] = man["items"][:2]                                          # yalnız ilk vuruşun sesleri
    put(ep, man)
    assert rules(ep, bible, t0=0, t1=DUR) == [] and rules(ep, bible) == ["REPLIK_EKSIK"]


def test_dialogue_without_a_resolvable_speaker_is_not_silently_dropped(tmp_path):
    _root, ep, sheet, bible, _a, _b = project(tmp_path, "kisa_uzun")
    sheet["beats"][1].update(characters=[], dialogue="Kim var orada?")
    (ep / "beat_sheet.json").write_text(json.dumps(sheet, ensure_ascii=False), encoding="utf-8")
    put(ep, real_manifest(ep, bible))
    assert rules(ep, bible) == ["DIYALOG_AYRISTIRILAMADI"]


def test_language_copy_and_untranslated_lines(tmp_path):
    _root, ep, sheet, bible, _a, _b = project(tmp_path, "iki_yetiskin")
    copy = ep / "lang" / "de"
    copy.mkdir(parents=True)
    sheet.update(language="de", untranslated_beats=[2])
    (copy / "beat_sheet.json").write_text(json.dumps(sheet, ensure_ascii=False), encoding="utf-8")
    man = real_manifest(copy, bible, lang="tr")                              # Türkçe liste Almanca kopyaya konmuş
    put(copy, man)
    assert rules(copy, bible) == ["CEVRILMEMIS_REPLIK", "YANLIS_DIL_SESI"]


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_estimate_is_marked_needs_permission_and_never_overwrites_real_audio(tmp_path, name):
    _root, ep, _sheet, bible, _a, _b = project(tmp_path, name)
    man = dc.write_estimate(str(ep), bible)
    assert man["status"] == "ESTIMATED" and man["lines"] == 3 and all(i["timing"] == "estimated" and "wav" not in i for i in man["items"])
    assert rules(ep, bible) == ["TAHMINI_SES"]
    rep = dc.check(str(ep), bible, allow_estimated=True)
    assert rep["problems"] == [] and rep["voice"] == "estimated"
    man["status"] = "PASSED"                                                  # üst durum değiştirilse de satır işareti kalır
    put(ep, man)
    assert rules(ep, bible) == ["TAHMINI_SES"]
    put(ep, real_manifest(ep, bible))
    before = (ep / "voice_manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        dc.write_estimate(str(ep), bible)
    assert (ep / "voice_manifest.json").read_bytes() == before


def test_estimate_speed_comes_from_project_data(tmp_path):
    _root, _ep, sheet, bible, _a, _b = project(tmp_path, "kisa_uzun")
    slow = dc.estimate_manifest(sheet, dict(bible, speech_estimate={"per_char_s": 0.2}))
    fast = dc.estimate_manifest(sheet, bible)
    assert all(s["duration_s"] > f["duration_s"] for s, f in zip(slow["items"], fast["items"]))


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_render_gate_stops_missing_dialogue_and_marks_draft(tmp_path, name, monkeypatch):
    root, ep, _sheet, bible, _a, _b = project(tmp_path, name)
    reached = []
    monkeypatch.setattr(render_worker.r2, "render_window", lambda plan_, des_, out_, **k: os.makedirs(out_, exist_ok=True) or reached.append(1) or {"missing": 1})
    monkeypatch.delenv("AHOS_ALLOW_ESTIMATED_VOICE", raising=False)

    def go():
        return render_worker.run(str(ep), bible, 0, DUR, str(root))
    out = go()
    assert out["error"] == "DIYALOG_EKSIK_VEYA_HATALI" and not reached and "SES_LISTESI_YOK" in out["problems"][0], out
    assert os.path.exists(ep / "render" / "dialogue_gate.json")
    dc.write_estimate(str(ep), bible)
    out = go()
    assert "TAHMINI_SES" in out["problems"][0] and not reached, out
    monkeypatch.setenv("AHOS_ALLOW_ESTIMATED_VOICE", "1")
    out = go()
    assert out.get("error") != "DIYALOG_EKSIK_VEYA_HATALI", out
    man = real_manifest(ep, bible)
    man["items"].pop(0)                                                       # taslak izni eksik repliği bağışlamaz
    put(ep, man)
    out = go()
    assert out["error"] == "DIYALOG_EKSIK_VEYA_HATALI" and "REPLIK_EKSIK" in out["problems"][0], out
