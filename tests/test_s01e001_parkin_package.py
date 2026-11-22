import copy, json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import s01e001_package as P, s01e001_data as D


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(); cls.out = tempfile.mkdtemp()
        cls.r = P.run(root=cls.root, out=cls.out)
        cls.pkg = P.build_package(cls.root, cls.out)

    def test_valid_and_exact(self):
        self.assertEqual(self.r["validation"]["status"], "PASSED", self.r["validation"]["problems"])
        self.assertEqual(self.r["validation"]["total_ms"], 480000); self.assertEqual(self.r["validation"]["scenes"], 12)

    def test_owner_scene_times_kept(self):
        got = [(s["exact_start_ms"] // 1000, s["exact_end_ms"] // 1000) for s in self.pkg["scenes"]]
        self.assertEqual(got[0], (0, 35)); self.assertEqual(got[5], (215, 255)); self.assertEqual(got[-1], (460, 480))

    def test_all_16_characters_appear(self):
        seen = {c for s in self.pkg["scenes"] for c in s["participating_character_ids"]}
        self.assertEqual(seen, set(D.ORDER))

    def test_required_scene_and_shot_fields(self):
        for s in self.pkg["scenes"]:
            for k in ("scene_id", "location_id", "environment_asset_ref", "exact_start_ms", "exact_end_ms", "participating_character_ids", "wardrobe_asset_refs",
                      "prop_asset_refs", "shot_list", "dialogue_lines", "acting_instructions", "facial_expressions", "body_motion", "camera", "lighting",
                      "ambience", "sound_effects", "music", "lip_sync", "continuity_requirements", "negative_constraints", "quality_requirements"):
                self.assertIn(k, s, (s["scene_id"], k))
            for sh in s["shots"]:
                for k in ("shot_id", "framing", "lens_perspective", "camera_movement", "character_positions", "movement_trajectory", "initial_pose",
                          "final_pose", "duration_ms", "visual_asset_refs", "voice_cue_refs", "transition"):
                    self.assertIn(k, sh, (sh["shot_id"], k))

    def test_validator_catches_violations(self):
        bad = copy.deepcopy(self.pkg)
        for l in bad["lines"]:
            if l["character_id"] == "kaan":
                l["text"] = "Ben de uçurtma uçurmak istiyorum"; break
        self.assertTrue(any("kaan" in e for e in P.validate(bad)))
        bad = copy.deepcopy(self.pkg); bad["lines"].append({"line_id": "x", "character_id": "ramin", "text": "Merhaba", "non_speech": False, "shot_id": "sc01_sh01", "start_ms": 0, "end_ms": 1})
        self.assertTrue(any("bebek" in e for e in P.validate(bad)))
        bad = copy.deepcopy(self.pkg); bad["scenes"][3]["exact_start_ms"] += 500
        self.assertTrue(P.validate(bad))
        bad = copy.deepcopy(self.pkg); bad["lines"][0]["end_ms"] = 10 ** 7
        self.assertTrue(any("sığmıyor" in e for e in P.validate(bad)))

    def test_babies_never_speak_and_are_introduced(self):
        for l in self.pkg["lines"]:
            if l["character_id"] in D.BABIES:
                self.assertTrue(l["non_speech"])
        txt = " ".join(l["text"] for l in self.pkg["lines"] if not l["non_speech"]).lower()
        self.assertIn("medine", txt); self.assertIn("ramin", txt)

    def test_missing_roster_reported_not_faked(self):
        st = P.character_status(self.root)
        self.assertTrue(all(c["approved_visual_path"] is None and not c["file_exists"] for c in st["characters"]))
        self.assertIn("MISSING", self.r["readiness"]["not_ready"][0]["state"])

    def test_roster_sha_verified(self):
        root = tempfile.mkdtemp(); d = os.path.join(root, P.ROSTER, "characters"); os.makedirs(d)
        open(os.path.join(d, "01_aden.png"), "wb").write(b"abc")
        json.dump({"status": "X", "characters": [{"id": "aden", "age": 3, "file": "characters/01_aden.png", "sha256": P._sha(os.path.join(d, "01_aden.png")), "status": "S"}]},
                  open(os.path.join(root, P.ROSTER, "manifest.json"), "w"))
        a = [c for c in P.character_status(root)["characters"] if c["character_id"] == "aden"][0]
        self.assertTrue(a["file_exists"]); self.assertTrue(a["sha256_matches_manifest"])
        open(os.path.join(d, "01_aden.png"), "wb").write(b"changed")
        a = [c for c in P.character_status(root)["characters"] if c["character_id"] == "aden"][0]
        self.assertFalse(a["sha256_matches_manifest"])

    def test_fatos_conflict_detection(self):
        root = tempfile.mkdtemp(); os.makedirs(os.path.join(root, "docs")); os.makedirs(os.path.join(root, "studio", "canon"))
        open(os.path.join(root, "docs", "KARAKTER-KANONU.md"), "w", encoding="utf-8").write("Fatoş başörtülü\n")
        open(os.path.join(root, "studio", "canon", "p7-owner-constraints.json"), "w", encoding="utf-8").write('"fatos": "30 yaş; BAŞÖRTÜSÜZ"\n')
        r = P.fatos_headscarf_check(root)
        self.assertTrue(r["conflict"]); self.assertIn("BAŞÖRTÜSÜZ", r["decision"])

    def test_all_output_files_written(self):
        for n in ("production_package.json", "scene_shot_manifest.json", "character_status.json", "continuity_matrix.json", "voice_lipsync_plan.json",
                  "audio_music_plan.json", "production_tasks_workers.json", "readiness.json", "validation_report.json", "SENARYO-FINAL-TASLAK.md",
                  "character_differentiation_proposals.json", "environment_library.json", "fatos_headscarf_check.json"):
            self.assertTrue(os.path.exists(os.path.join(self.out, n)), n)

    def test_deterministic(self):
        a = json.dumps(P.build_package(self.root, self.out), sort_keys=True); b = json.dumps(P.build_package(self.root, self.out), sort_keys=True)
        self.assertEqual(a, b)

    def test_fidelity_checker_accepts_own_script(self):
        import script_fidelity as sf
        src = open(os.path.join(self.out, "SENARYO-FINAL-TASLAK.md"), encoding="utf-8").read()
        self.assertEqual(sf.check(src, [{"dialogue": " | ".join(l["character_id"] + ": " + l["text"] for l in self.pkg["lines"])}])["status"], "PASSED")


if __name__ == "__main__":
    unittest.main()
