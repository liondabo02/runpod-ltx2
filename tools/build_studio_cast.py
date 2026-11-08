"""16 karakterlik stüdyo hazırlık paketini üretir (spekülatif görsel üretmez)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "studio"
DATE = "2026-11-08"

CAST = [
    ("aden", "Aden", 3.0, "girl", "lead child", "merkez aile", "3 yaş kız; tek sarı yıldız toka, sol yanakta 3 çil, omuz hizası dalgalı koyu kahve saç, kobalt tişört"),
    ("kaan", "Kaan", 1.0, "boy", "lead child", "merkez aile", "1 yaş erkek; bebeksi oran (3,0 kafa), kısa kıvırcık siyah saç, mercan tişört"),
    ("esra", "Esra", 33.0, "woman", "mother", "merkez aile", "Aden ve Kaan'ın annesi; başörtülü, sıcak ve sakin"),
    ("ahmet", "Ahmet", 33.0, "man", "father", "merkez aile", "Aden ve Kaan'ın babası; sakin, destekleyici"),
    ("esma", "Esma", 29.0, "woman", "aunt", "merkez aile", "Teyze; başörtülü, neşeli ama yumuşak"),
    ("harun", "Harun", 30.0, "man", "uncle", "merkez aile", "Dayı; uzun boylu, uzun saçlı, güçlü ve sıcak"),
    ("veysel", "Veysel", 33.0, "man", "family friend", "veysel ailesi", "Yetişkin aile karakteri; Salih ve Medine'nin babası"),
    ("oznur", "Öznur", 31.0, "woman", "family friend", "veysel ailesi", "Başörtülü yetişkin; Salih ve Medine'nin annesi"),
    ("salih", "Salih", 2.0, "boy", "child", "veysel ailesi", "Yaklaşık 2 yaş erkek çocuk"),
    ("medine", "Medine", 2 / 12, "girl", "baby", "veysel ailesi", "Bebek kız; yalnız agu/coo ve kısa tepkiler"),
    ("davut", "Davut", 30.0, "man", "family friend", "davut ailesi", "Uzun saçlı, iri yapılı yetişkin; Emoş, Berzan, Aras ve Ramin'in babası"),
    ("fatos", "Fatoş", 30.0, "woman", "family friend", "davut ailesi", "Yetişkin kadın; Davut'un eşi, dört çocuğun annesi"),
    ("emos", "Emoş", 4.0, "girl", "child", "davut ailesi", "Yaklaşık 4 yaş kız; Aden'den ayrı, enerjik"),
    ("berzan", "Berzan", 2.0, "boy", "child", "davut ailesi", "Yaklaşık 2 yaş erkek; Aras'ın ikizi, daha hareketli"),
    ("aras", "Aras", 2.0, "boy", "child", "davut ailesi", "Yaklaşık 2 yaş erkek; Berzan'ın ikizi, daha sakin"),
    ("ramin", "Ramin", 1 / 12, "boy", "baby", "davut ailesi", "Yenidoğan bebek; yalnız agu, nefes ve kısa tepkiler"),
]

RELATIONS = [
    ("aden", "sibling_of", "kaan"), ("ahmet", "father_of", "aden"), ("ahmet", "father_of", "kaan"),
    ("aras", "twin_of", "berzan"), ("berzan", "twin_of", "aras"),
    ("davut", "parent_of", "aras"), ("davut", "parent_of", "berzan"), ("davut", "parent_of", "emos"),
    ("davut", "parent_of", "ramin"), ("davut", "partner_of", "fatos"),
    ("esma", "aunt_of", "aden"), ("esma", "aunt_of", "kaan"),
    ("esra", "mother_of", "aden"), ("esra", "mother_of", "kaan"),
    ("fatos", "parent_of", "aras"), ("fatos", "parent_of", "berzan"), ("fatos", "parent_of", "emos"),
    ("fatos", "parent_of", "ramin"), ("fatos", "partner_of", "davut"),
    ("harun", "uncle_of", "aden"), ("harun", "uncle_of", "kaan"),
    ("kaan", "sibling_of", "aden"),
    ("oznur", "parent_of", "medine"), ("oznur", "parent_of", "salih"), ("oznur", "partner_of", "veysel"),
    ("veysel", "parent_of", "medine"), ("veysel", "parent_of", "salih"), ("veysel", "partner_of", "oznur"),
]

VOICE = {
    "aden": ("girl", "bright, curious, playful lead; tiny natural child voice"),
    "kaan": ("boy", "soft cheerful toddler; early words, little laughs"),
    "esra": ("woman", "warm reassuring mother, calm and patient"),
    "ahmet": ("man", "kind relaxed father, grounded warmth"),
    "esma": ("woman", "friendly warm aunt, lively but gentle"),
    "harun": ("man", "warm confident anchor, calm humor"),
    "veysel": ("man", "friendly sociable adult, distinct from Ahmet/Harun"),
    "oznur": ("woman", "warm composed adult woman, clear"),
    "salih": ("boy", "playful two-year-old, short phrases"),
    "medine": ("girl", "infant coos and tiny laughs; no speech"),
    "davut": ("man", "good-humored relaxed adult, warm comic timing"),
    "fatos": ("woman", "friendly expressive adult woman"),
    "emos": ("girl", "energetic four-year-old, distinct from Aden"),
    "berzan": ("boy", "brighter impulsive twin, short phrases"),
    "aras": ("boy", "softer calmer twin, short phrases"),
    "ramin": ("boy", "newborn coos, breaths, fussing; no speech"),
}

AGES = {row[0]: row[2] for row in CAST}
STAGES = {"aden": "preschool", "kaan": "toddler", "esra": "adult", "ahmet": "adult", "esma": "adult",
          "harun": "adult", "veysel": "adult", "oznur": "adult", "salih": "toddler", "medine": "infant",
          "davut": "adult", "fatos": "adult", "emos": "preschool", "berzan": "toddler", "aras": "toddler",
          "ramin": "infant"}

HIJAB = {"esra", "esma", "oznur"}
LONG_HAIR = {"harun", "davut"}
LEAD = {"aden", "kaan"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text_safely(path: Path, content: str) -> None:
    """Idempotent by default; protect owner edits and approval records on reruns."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        previous = path.read_text(encoding="utf-8")
        if previous != content:
            raise FileExistsError(
                f"Existing file differs; refusing to overwrite: {path}. "
                "Review and merge the change explicitly."
            )
        return
    path.write_text(content, encoding="utf-8")


def write(path: Path, payload) -> None:
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    write_text_safely(path, content)


def motion_for(stage: str) -> dict:
    if stage == "infant":
        return {"allowed": ["sırtüstü uzanma", "baş çevirme", "uzanma", "kısa gülüş/agu", "yetişkin kucağında taşınma"],
                "forbidden": ["yürüme", "koşma", "tek başına oturma", "ip/toksa tutma"],
                "signature": "kısa nefes ve agu; beden dili sade"}
    if stage == "toddler":
        return {"allowed": ["emekleme", "tutunarak yürüme", "yalpalayarak yürüme", "oturma", "işaret etme", "el çırpma", "kısa gülüş"],
                "forbidden": ["koşma", "zıplama", "uzun cümle", "küçük parça tutma", "ip çekme"],
                "signature": "iki eliyle büyük nesne tutma; yetişkin desteğiyle denge"}
    if stage == "preschool":
        return {"allowed": ["yürüme", "hafif koşu", "zıplama", "oturma", "dönme", "işaret etme", "el çırpma", "sarılma"],
                "forbidden": ["yetişkin gücü", "tehlikeli tırmanma", "uzun/karmaşık cümle"],
                "signature": "meraklı öne eğilme; sevinçte küçük zıplama"}
    return {"allowed": ["yürüme", "koşma", "eğilme", "oturma", "kucaklama", "işaret etme", "baş sallama"],
            "forbidden": ["çocuk oranı", "aşırı abartılı mimik", "gençlik jestleri"],
            "signature": "sakin ağırlık aktarımı; sıcak duruş"}


def build() -> None:
    aden = load(ROOT / "characters" / "aden.json")
    kaan = load(ROOT / "characters" / "kaan.json")
    audio_root = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\control_plane_v2"
                      r"\runtime\private\animation-studio\audio\core-voices")
    visual_root = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\control_plane_v2"
                       r"\runtime\private\animation-studio\model-sheets")

    cast_rows = []
    for cid, name, age, gender, role, group, brief in CAST:
        stage = STAGES[cid]
        voice_ref = audio_root / cid / "tr.wav"
        has_voice = voice_ref.is_file()
        has_visual = (visual_root / f"{cid}-reference-flux-seed-78.png").is_file() if cid == "aden" else (
            (visual_root / f"{cid}-reference-flux-seed-80.png").is_file() if cid == "kaan" else False)
        canon = aden if cid == "aden" else kaan if cid == "kaan" else None
        visual_dna = {"owner_brief": brief, "status": "READY_FOR_QA" if canon else "MISSING",
                      "source": "characters/aden.json" if cid == "aden" else
                                "characters/kaan.json" if cid == "kaan" else "owner brief; görsel kanon yok"}
        if canon:
            visual_dna.update({"palette": canon["palette"], "face": canon["face"], "hair": canon["hair"],
                               "clothing": canon["clothing"], "proportions": canon["proportions"]})
        palette = canon["palette"] if canon else {"status": "MISSING", "note": "kanonik palet henüz yok"}
        motion = motion_for(stage)
        voice = {"engine_voice_direction": VOICE[cid][1], "gender_presentation": VOICE[cid][0],
                 "reference_wav": str(voice_ref) if has_voice else None,
                 "reference_status": "READY_FOR_QA" if has_voice else "MISSING",
                 "languages": {"tr": "TEXT_READY", "de": "TEXT_PLANNED", "ar": "TEXT_PLANNED",
                               "fr": "TEXT_PLANNED", "es": "TEXT_PLANNED", "ku": "TEXT_PLANNED"},
                 "viseme_map": "PLANNED", "qa": "NOT_EVALUATED"}
        model = {"target": "Blender + glTF/GLB, reusable rig", "mesh": "MISSING", "rig": "MISSING",
                 "materials": "PLANNED", "face_rig": "PLANNED", "viseme_rig": "PLANNED",
                 "blend_file": None, "glb_file": None, "note": "Gerçek .blend/.glb yok; PNG 3D model sayılmaz."}
        character = {
            "schema": "ahos.studio.character.v1", "character_id": cid, "display_name": name,
            "age_years": round(age, 2), "age_stage": stage, "gender_presentation": gender,
            "role": role, "family_group": group, "lead": cid in LEAD,
            "hijab": cid in HIJAB, "long_hair": cid in LONG_HAIR,
            "height_cm": 98 if cid == "aden" else 76 if cid == "kaan" else None,
            "height_status": "READY_FOR_QA" if cid in LEAD else "MISSING",
            "proportions": canon["proportions"] if canon else {"status": "MISSING"},
            "status": {"canon": "READY", "visual_dna": visual_dna["status"],
                       "palette": "READY_FOR_QA" if canon else "MISSING",
                       "motion": "SPEC_READY", "voice": voice["reference_status"],
                       "model_3d": "MISSING", "owner_approval": "NONE"},
            "source_refs": ["studio/canon/cast-manifest.json"]
        }
        base = OUT / "characters" / cid
        write(base / "character.json", character)
        write(base / "visual-dna.json", visual_dna)
        write(base / "color-palette.json", palette)
        write(base / "motion-profile.json", {"schema": "ahos.motion.v1", "character_id": cid,
                                             "age_stage": stage, **motion, "status": "SPEC_READY"})
        write(base / "voice-profile.json", {"schema": "ahos.voice.v1", "character_id": cid,
                                            "age_stage": stage, **voice})
        write(base / "model-spec.json", {"schema": "ahos.model-spec.v1", "character_id": cid,
                                         "age_stage": stage, **model})
        cast_rows.append({"character_id": cid, "display_name": name, "age_years": round(age, 2),
                          "age_stage": stage, "gender_presentation": gender, "role": role,
                          "family_group": group, "lead": cid in LEAD, "hijab": cid in HIJAB,
                          "long_hair": cid in LONG_HAIR,
                          "height_cm": character["height_cm"], "height_status": character["height_status"],
                          "status": character["status"]})

    write(OUT / "canon" / "cast-manifest.json", {
        "schema": "ahos.studio.cast.v1", "generated_at": DATE, "character_count": len(cast_rows),
        "characters": cast_rows, "note": "Yalnız Aden/Kaan görsel kanona sahip; diğerleri MISSING."})
    write(OUT / "canon" / "family-relations.json", {
        "schema": "ahos.studio.relations.v1", "count": len(RELATIONS),
        "relations": [{"from": a, "type": t, "to": b} for a, t, b in RELATIONS]})
    write(OUT / "canon" / "continuity-rules.json", {
        "schema": "ahos.studio.continuity.v1",
        "palette_rule": "Aden/Kaan paletleri characters/*.json; diğer karakterler MISSING.",
        "scale_rule": {"aden_cm": 98, "kaan_cm": 76, "adult_cm": "MISSING"},
        "kaan_limits": ["1 yaş; koşma/zıplama yok", "yalnız dört kısa ses: Kuş!, Aa!, Mavi!, Ya!",
                        "ip/boyun/el dolanması yok"],
        "tail_strips": {"count": 6, "blanket": ["kırmızı", "sarı", "mavi"],
                        "grass": ["yeşil", "turuncu"], "bush": ["mor"]},
        "residence": {"claim": "Aden ailesi Harun'un evinde yaşıyor",
                      "status": "UNVERIFIED", "evidence": "character-memory.db canon_facts ve docs taramasında kayıt yok",
                      "rule": "Doğrulanmadan sahne kanonu yapılmaz."},
        "owner_approval": "NONE"})
    write(OUT / "canon" / "visual-style-bible.md", STYLE_BIBLE)
    write(OUT / "canon" / "voice-style-bible.md", VOICE_BIBLE)

    assets = [
        {"asset_id": "park-kite-scene", "kind": "environment_spec", "path": "characters/scenes/park-kite-01.json",
         "status": "SPEC_READY", "note": "Palet/ışık/prompt kanonu; 3D set yok"},
        {"asset_id": "kite-six-strip-tail", "kind": "prop_spec", "path": "studio/canon/continuity-rules.json",
         "status": "SPEC_READY", "note": "Altı şerit; 3D mesh yok"},
        {"asset_id": "aden-keyframe-v1", "kind": "image",
         "path": "deliverables/S01-PARK-KITE-001/keyframes/keyframe-girl-seed-77.png",
         "status": "READY_FOR_QA", "note": "v1 görsel; v2 model sheet değil"},
        {"asset_id": "take2-5s-test", "kind": "video",
         "path": "deliverables/S01-PARK-KITE-001/park-kite-take2-girl-1080p.mp4",
         "status": "VIDEO_RENDERED_TEST", "note": "5 sn teknik test; 30 sn pilot değil"},
        {"asset_id": "voice-refs-tr", "kind": "audio_refs",
         "path": "private animation-studio/audio/core-voices", "status": "READY_FOR_QA",
         "note": "14 karakterde tr.wav; Medine/Ramin yok; onay yok"},
    ]
    write(OUT / "production" / "asset-registry.json", {
        "schema": "ahos.studio.assets.v1", "assets": assets,
        "note": "Yalnız gerçek dosya yolu olanlar listelendi; 3D mesh/rig yok."})

    matrix = []
    for row in cast_rows:
        cid = row["character_id"]
        matrix.append({
            "character_id": cid,
            "canon": "READY",
            "visual_reference": "NEEDS_REVISION" if cid in {"aden", "kaan"} else "MISSING",
            "model_sheet": "NEEDS_REVISION" if cid in {"aden", "kaan"} else "MISSING",
            "expression_sheet": "MISSING",
            "voice_reference": "READY_FOR_QA" if (audio_root / cid / "tr.wav").is_file() else "MISSING",
            "mesh_3d": "MISSING", "rig": "MISSING", "animation_library": "MISSING",
            "multilingual_audio": "MISSING", "qa": "NOT_EVALUATED", "owner_approval": "NONE",
        })
    write(OUT / "production" / "cast-readiness.json", {
        "schema": "ahos.studio.readiness.v1", "generated_at": DATE,
        "columns": ["canon", "visual_reference", "model_sheet", "expression_sheet", "voice_reference",
                    "mesh_3d", "rig", "animation_library", "multilingual_audio", "qa", "owner_approval"],
        "rows": matrix,
        "summary": {"characters": 16, "visual_reference_present": 2, "visual_ready": 0,
                    "voice_ready": 14, "mesh_ready": 0, "rig_ready": 0, "approved": 0}})

    episode = load(ROOT / "studio" / "s01e001" / "episode-v2.json")
    opening = load(ROOT / "studio" / "s01e001" / "episode-open-30s-v2.json")
    shots = []
    for scene in episode["scenes"]:
        for index, beat in enumerate(scene["beats"], 1):
            shots.append({
                "shot_id": f"{scene['scene_id']}-SH{index:02d}",
                "scene_id": scene["scene_id"], "start_seconds": beat["start_seconds"],
                "duration_seconds": beat["duration_seconds"], "action": beat["action"],
                "focus": beat["focus"], "kaan_action": beat["kaan_action"],
                "cast_ids": scene["cast_ids"], "camera": "çocuk göz hizası; 180° kuralı; ışık soldan",
                "status": "BOARD_SPEC_READY", "storyboard_image": None,
            })
    write(OUT / "s01e001" / "storyboard" / "shot-schedule.json", {
        "schema": "ahos.studio.shot-schedule.v1", "episode_id": "S01E001",
        "target_seconds": 480, "shot_count": len(shots), "shots": shots,
        "opening": {"kind": "EPISODE-OPEN-30s", "source": "studio/s01e001/episode-open-30s-v2.json",
                    "shots": opening["shots"]},
        "note": "Storyboard görselleri yok; board spec hazır."})
    lines = ["# S01E001 storyboard / shot schedule", "",
             f"Toplam {len(shots)} çekim · 480 sn · görsel board yok (SPEC_READY).", "",
             "| Çekim | Sahne | Sn | Süre | Aksiyon |", "|---|---|---|---|---|"]
    for shot in shots:
        lines.append(f"| {shot['shot_id']} | {shot['scene_id']} | {shot['start_seconds']} | "
                     f"{shot['duration_seconds']} | {shot['action']} |")
    write_text_safely(OUT / "s01e001" / "storyboard" / "storyboard.md", "\n".join(lines) + "\n")

    work_orders = []
    for row in cast_rows:
        cid = row["character_id"]
        work_orders.append({
            "work_order_id": f"WO-{cid}-visual", "character_id": cid,
            "owner_role": "Character Art", "output": f"studio/characters/{cid}/model-sheets/",
            "status": "BLOCKED",
            "blocker": ("v1 görsel var ama v2 model sheet ve sahip onayı yok"
                        if cid in {"aden", "kaan"} else
                        "kanonik görsel referans yok; ücretsiz üretim yolu kapalı"),
            "cost_eur": 0})
        work_orders.append({
            "work_order_id": f"WO-{cid}-3d", "character_id": cid,
            "owner_role": "3D Modeling & Rigging", "output": f"studio/characters/{cid}/3d/",
            "status": "PLANNED", "blocker": "Blender kurulu değil; model spec hazır", "cost_eur": 0})
        work_orders.append({
            "work_order_id": f"WO-{cid}-voice", "character_id": cid,
            "owner_role": "Voice & Localization", "output": f"studio/characters/{cid}/voice/",
            "status": "READY_FOR_QA" if (audio_root / cid / "tr.wav").is_file() else "MISSING",
            "blocker": None if (audio_root / cid / "tr.wav").is_file() else "referans ses yok",
            "cost_eur": 0})
    write(OUT / "production" / "work-orders.json", {
        "schema": "ahos.studio.work-orders.v1", "count": len(work_orders),
        "orders": work_orders, "note": "Sahip onayı gerektiren üretimler BLOCKED."})
    write(OUT / "production" / "approvals.json", {
        "schema": "ahos.studio.approvals.v1", "approvals": [],
        "note": "Hiçbir karakter veya varlık sahip onayı almadı."})
    write(OUT / "production" / "production-status.json", {
        "schema": "ahos.studio.production-status.v1", "generated_at": DATE,
        "studio": "SPEC_READY", "character_canon": "16/16", "visual_reference": "2/16 READY_FOR_QA",
        "voice_reference": "14/16 READY_FOR_QA", "mesh_3d": "0/16", "rig": "0/16",
        "s01e001_script": "DRAFT_FOR_OWNER_APPROVAL", "s01e001_storyboard": "BOARD_SPEC_READY",
        "video": "NONE", "owner_approval": "NONE", "spend_eur": 0,
        "blockers": ["ZeroGPU kotası kapalı", "yerel CUDA yok", "Blender kurulu değil",
                     "16 karakterin 14'ünde görsel kanon yok", "58 beat beklentisi vs 55 gerçek"]})
    readme = f"""# AHOS Çizgi Film Stüdyosu — 16 karakter hazırlık paketi

Durum: **SPEC_READY** · sahip onayı yok · harcama **0 EUR**

| Alan | Gerçek durum |
|---|---|
| Karakter kanonu | 16/16 READY |
| Görsel referans | 2/16 (Aden, Kaan) READY_FOR_QA; 14 MISSING |
| Ses referansı | 14/16 READY_FOR_QA; Medine/Ramin MISSING |
| 3D mesh / rig | 0/16 MISSING |
| S01E001 senaryo | v2, 480 sn, 55 beat (emirde 58 yazıyor — çelişki) |
| Storyboard | {len(shots)} çekim, board görseli yok |
| Video | yok; yalnız 5 sn teknik take2 |

## Dizinler

- `studio/canon/` — cast-manifest, family-relations, continuity-rules, style bibles
- `studio/characters/<id>/` — character, visual-dna, palette, motion, voice, model-spec
- `studio/production/` — readiness, asset-registry, work-orders, approvals, status
- `studio/s01e001/storyboard/` — shot-schedule + storyboard.md

## Engeller

- ZeroGPU kotası kapalı; ücretli yol yasak.
- Yerel CUDA/Blender/SDXL yok.
- 14 karakterde görsel kanon yok; model sheet üretilemez.
- **Kanıt:** `studio/production/cast-readiness.json`, `asset-registry.json`.
"""
    write_text_safely(OUT / "README.md", readme)

    print(json.dumps({"characters": len(cast_rows), "relations": len(RELATIONS),
                      "shots": len(shots), "out": str(OUT)}, ensure_ascii=False))


STYLE_BIBLE = """# AHOS Stüdyo — Görsel Stil Kılavuzu (v1, taslak)

- **Yaş grubu:** 2–5; yuvarlatılmış formlar, büyük okunaklı gözler, sade siluet.
- **Palet:** sıcak sabah ışığı; doygunluğu kontrollü; her sahne için tek ana renk + iki destek.
- **Işık:** sol arka üstten 5200K; gölge yönü sahne boyunca sabit.
- **Kamera:** çocuk göz hizası 0,95 m; 180° kuralı; her çekim 5–10 sn.
- **Arka plan:** temiz, düşük kontrast; karakteri yutmayan.
- **Yasak:** fotogerçekçilik, keskin köşe, aşırı parlaklık, marka/logotype, kopya karakter.
- **Durum:** metin spec; gerçek stil kareleri üretilmedi.
"""

VOICE_BIBLE = """# AHOS Stüdyo — Ses Stili Kılavuzu (v1, taslak)

- Her karakterin sabit ses kimliği vardır; bölümden bölüme değişmez.
- Aden: doğal küçük kız, parlak ama cıyak değil.
- Kaan: 1 yaş; kısa ses/kelime, gülüş; cümle yok.
- Esra: sıcak, sakin anne; Ahmet: sakin baba; ikisi ayrı tını.
- Bebekler (Medine, Ramin): yalnız agu/nefes; sözlü replik yok.
- Diller: tr, de, ar, fr, es, ku (Kurmancî ayrı uzman QA).
- Hiçbir ses, insan onayı olmadan "onaylı" sayılmaz.
- Durum: metin spec; seslendirme üretilmedi.
"""


if __name__ == "__main__":
    build()
