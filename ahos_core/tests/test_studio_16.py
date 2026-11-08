"""16 karakterlik stüdyo hazırlık paketi: kanon, dürüstlük ve sahne sürekliliği."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDIO = ROOT / "studio"

EXPECTED = {
    "aden": (3.0, "girl"), "kaan": (1.0, "boy"), "esra": (33.0, "woman"), "ahmet": (33.0, "man"),
    "esma": (29.0, "woman"), "harun": (30.0, "man"), "veysel": (33.0, "man"), "oznur": (31.0, "woman"),
    "salih": (2.0, "boy"), "medine": (0.17, "girl"), "davut": (30.0, "man"), "fatos": (30.0, "woman"),
    "emos": (4.0, "girl"), "berzan": (2.0, "boy"), "aras": (2.0, "boy"), "ramin": (0.08, "boy"),
}


def load(*parts: str) -> dict:
    return json.loads((STUDIO.joinpath(*parts)).read_text(encoding="utf-8"))


def test_cast_manifest_has_16_unique_characters():
    manifest = load("canon", "cast-manifest.json")
    assert manifest["character_count"] == 16
    assert len(manifest["characters"]) == 16
    ids = [row["character_id"] for row in manifest["characters"]]
    assert len(set(ids)) == 16
    assert set(ids) == set(EXPECTED)


def test_ages_and_genders_match_canon():
    rows = {row["character_id"]: row for row in load("canon", "cast-manifest.json")["characters"]}
    for cid, (age, gender) in EXPECTED.items():
        assert abs(rows[cid]["age_years"] - age) <= 0.02, cid
        assert rows[cid]["gender_presentation"] == gender, cid
    assert rows["aden"]["height_cm"] == 98 and rows["kaan"]["height_cm"] == 76
    assert rows["aden"]["lead"] and rows["kaan"]["lead"]


def test_hijab_and_long_hair_flags():
    rows = {row["character_id"]: row for row in load("canon", "cast-manifest.json")["characters"]}
    assert {cid for cid, row in rows.items() if row["hijab"]} == {"esra", "oznur"}
    assert {cid for cid, row in rows.items() if row["long_hair"]} == {"harun", "davut"}


def test_family_relations_are_complete_and_locked():
    relations = load("canon", "family-relations.json")
    assert relations["count"] == 28
    pairs = {(row["from"], row["type"], row["to"]) for row in relations["relations"]}
    assert ("esra", "mother_of", "aden") in pairs
    assert ("ahmet", "father_of", "kaan") in pairs
    assert ("harun", "uncle_of", "aden") in pairs
    assert ("berzan", "twin_of", "aras") in pairs
    assert ("davut", "parent_of", "ramin") in pairs


def test_no_fake_3d_or_approval():
    readiness = load("production", "cast-readiness.json")
    assert readiness["summary"]["mesh_ready"] == 0
    assert readiness["summary"]["rig_ready"] == 0
    assert readiness["summary"]["approved"] == 0
    assert readiness["summary"]["visual_ready"] == 0
    rows = {row["character_id"]: row for row in readiness["rows"]}
    for cid in ("aden", "kaan"):
        assert rows[cid]["model_sheet"] == "NEEDS_REVISION"
    assert all(row["mesh_3d"] == "MISSING" and row["owner_approval"] == "NONE" for row in readiness["rows"])
    assert load("production", "approvals.json")["approvals"] == []
    text = (STUDIO / "README.md").read_text(encoding="utf-8")
    assert "APPROVED" not in text


def test_residence_claim_is_unverified():
    continuity = load("canon", "continuity-rules.json")
    assert continuity["residence"]["status"] == "UNVERIFIED"
    assert "Harun" in continuity["residence"]["claim"]


def test_episode_duration_but_beat_count_mismatch_is_reported():
    episode = load("s01e001", "episode-v2.json")
    assert sum(scene["duration_seconds"] for scene in episode["scenes"]) == 480
    beats = sum(len(scene["beats"]) for scene in episode["scenes"])
    assert beats == 55
    status = load("production", "production-status.json")
    assert any("58" in blocker and "55" in blocker for blocker in status["blockers"])


def test_tail_six_strips_and_storyboard():
    continuity = load("canon", "continuity-rules.json")
    strips = continuity["tail_strips"]
    assert strips["count"] == 6
    assert strips["blanket"] == ["kırmızı", "sarı", "mavi"]
    assert strips["grass"] == ["yeşil", "turuncu"] and strips["bush"] == ["mor"]
    schedule = load("s01e001", "storyboard", "shot-schedule.json")
    assert schedule["shot_count"] == 55 == len(schedule["shots"])
    assert sum(shot["duration_seconds"] for shot in schedule["shots"]) == 480
    assert len(schedule["opening"]["shots"]) == 6
    assert sum(shot["duration_seconds"] for shot in schedule["opening"]["shots"]) == 30


def test_voice_profiles_cover_all_16_and_babies_have_no_speech():
    for cid in EXPECTED:
        profile = load("characters", cid, "voice-profile.json")
        assert profile["character_id"] == cid
    kaan = load("characters", "kaan", "voice-profile.json")
    assert kaan["age_stage"] == "toddler"
    for baby in ("medine", "ramin"):
        profile = load("characters", baby, "voice-profile.json")
        assert profile["age_stage"] == "infant"
        assert "no speech" in profile["engine_voice_direction"]


def test_style_bibles_and_work_orders_exist():
    assert (STUDIO / "canon" / "visual-style-bible.md").is_file()
    assert (STUDIO / "canon" / "voice-style-bible.md").is_file()
    orders = load("production", "work-orders.json")
    assert orders["count"] == 48
    assert all(order["cost_eur"] == 0 for order in orders["orders"])
