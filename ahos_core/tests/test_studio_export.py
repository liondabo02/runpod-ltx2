"""Kurgu dışa aktarımı: EDL, çekim listesi, storyboard."""

from __future__ import annotations

from pathlib import Path

from ahos.studio_export import export_all, export_edl, export_shotlist, export_storyboard

MANIFEST = {
    "title": "Test Bölüm",
    "fps": 24,
    "duration_seconds": 6.0,
    "resolution": [1280, 720],
    "scenes_detail": [
        {"scene_id": "s1", "setting": "Açılış", "seconds": 3.0},
        {"scene_id": "s2", "setting": "Kapanış", "seconds": 3.0},
    ],
}

TIMELINE = [
    {"scene_id": "s1", "speaker": "aden", "text": "Merhaba", "start": 0.0, "end": 3.0},
    {"scene_id": "s2", "speaker": "kaan", "text": "Hoşça kal", "start": 3.0, "end": 6.0},
]


def test_edl_has_one_event_per_scene_and_valid_timecodes(tmp_path):
    path = export_edl(MANIFEST, tmp_path / "episode.edl")
    body = path.read_text(encoding="utf-8")

    assert body.startswith("TITLE: Test Bölüm")
    assert "FCM: NON-DROP FRAME" in body
    assert body.count("V     C") == 2
    assert "00:00:00:00 00:00:03:00" in body
    assert "00:00:03:00 00:00:06:00" in body
    assert "* FROM CLIP NAME: Test Bölüm sahne s1" in body


def test_shotlist_is_a_spreadsheet_with_one_row_per_line(tmp_path):
    path = export_shotlist(MANIFEST, TIMELINE, tmp_path / "shotlist.csv")
    rows = path.read_text(encoding="utf-8").strip().splitlines()

    assert rows[0] == "scene,speaker,text,start_seconds,end_seconds,duration"
    assert len(rows) == 3
    assert rows[1].startswith("s1,aden,Merhaba,0.00,3.00,3.00")
    assert rows[2].startswith("s2,kaan,")


def test_storyboard_keeps_scene_detail_and_lines(tmp_path):
    path = export_storyboard(MANIFEST, TIMELINE, tmp_path / "storyboard.json")
    payload = path.read_text(encoding="utf-8")

    assert '"title": "Test Bölüm"' in payload
    assert '"scene_id": "s1"' in payload
    assert '"text": "Merhaba"' in payload


def test_export_all_writes_three_files(tmp_path):
    result = export_all(MANIFEST, TIMELINE, tmp_path)
    assert set(result) == {"edl", "shotlist", "storyboard"}
    for value in result.values():
        assert Path(value).is_file()
