"""Fail-closed tests for owner-accepted roster and production evidence."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from studio_production_gate import IDS, assess


class ProductionGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / "studio/reference/owner_accepted_roster_v1"
        (self.base / "characters").mkdir(parents=True)
        self.poster = b"owner-approved-roster-image"
        (self.base / "AHOS_Studio16_Approved_Poster.png").write_bytes(self.poster)
        chars = []
        for idx, ident in enumerate(IDS, start=1):
            content = f"unique-image-{ident}".encode()
            filename = f"characters/{idx:02d}_{ident}.png"
            (self.base / filename).write_bytes(content)
            chars.append({"id": ident, "file": filename,
                "sha256": hashlib.sha256(content).hexdigest(),
                "status": "POSTER_CROP_NOT_INDEPENDENT_MODEL"})
        (self.base / "manifest.json").write_text(json.dumps({
            "status": "ROSTER_POSTER_OWNER_ACCEPTED",
            "source_sha256": hashlib.sha256(self.poster).hexdigest(),
            "characters": chars}), encoding="utf-8")

    def test_valid_roster_passes_storyboard_only(self):
        self.assertTrue(assess(self.root, "storyboard")["pass"])
        self.assertEqual(assess(self.root, "storyboard")["verified_characters"], 16)
        self.assertFalse(assess(self.root, "professional")["pass"])

    def test_crop_tampering_blocks_roster(self):
        (self.base / "characters/01_aden.png").write_bytes(b"tampered")
        result = assess(self.root, "storyboard")
        self.assertFalse(result["pass"])
        self.assertIn("crop_missing_or_hash_invalid:aden", result["issues"])

    def test_missing_roster_fails_closed(self):
        (self.base / "manifest.json").unlink()
        self.assertFalse(assess(self.root, "storyboard")["pass"])

    def test_poster_crop_cannot_forge_rig(self):
        registry = self.root / "studio/production/verified-assets.json"
        registry.parent.mkdir(parents=True)
        one = self.base / "characters/01_aden.png"
        registry.write_text(json.dumps({"characters": {"aden": {"rig": {
            "path": "studio/reference/owner_accepted_roster_v1/characters/01_aden.png",
            "sha256": hashlib.sha256(one.read_bytes()).hexdigest()}}}}),
            encoding="utf-8")
        report = assess(self.root, "professional")
        self.assertIn("roster_crop_not_production_asset:aden:rig", report["issues"])
        self.assertEqual(report["verified_stage_assets"]["rig"], 0)


if __name__ == "__main__":
    unittest.main()
