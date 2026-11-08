"""Studio-16 kanonunu OpenMontage hattına bağlayan köprü ve storyboard props üretir."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "studio"
OUT = STUDIO / "integration"
OPENMONTAGE = Path(
    r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects"
    r"\harun-ai-foundry\external-integrations\OpenMontage")


def main() -> int:
    cast = json.loads((STUDIO / "canon" / "cast-manifest.json").read_text(encoding="utf-8"))
    opening = json.loads((STUDIO / "s01e001" / "episode-open-30s-v2.json").read_text(encoding="utf-8"))
    readiness = json.loads((STUDIO / "production" / "cast-readiness.json").read_text(encoding="utf-8"))
    ready = {row["character_id"]: row for row in readiness["rows"]}

    bridge = {
        "schema": "ahos.studio.openmontage-bridge.v1",
        "generated_at": "2026-11-08",
        "target": {
            "system": "OpenMontage",
            "path": str(OPENMONTAGE),
            "pipeline": "pipeline_defs/character-animation.yaml",
            "license": "AGPLv3",
            "license_risk": "Ticari/SaaS kullanımda kaynak paylaşım yükümlülüğü; hukuk incelemesi gerekli.",
            "installed_state": {
                "python_package": True, "pipeline_defs": 13,
                "remotion_composer": True, "node_modules": True,
                "node_modules_source": "npm install --offline (199 paket; yeni indirme yok)",
                "remotion_cli": "BLOCKED — --version 90 sn içinde yanıt vermedi",
            },
        },
        "character_map": [
            {
                "character_id": row["character_id"],
                "display_name": row["display_name"],
                "age_stage": row["age_stage"],
                "canon_dir": f"studio/characters/{row['character_id']}/",
                "visual_status": ready[row["character_id"]]["visual_reference"],
                "voice_status": ready[row["character_id"]]["voice_reference"],
                "owner_approval": "NONE",
                "use_in_opening": row["character_id"] in {"aden", "kaan"},
            }
            for row in cast["characters"]
        ],
        "scene_map": {
            "episode": "S01E001",
            "opening_30s": "studio/s01e001/episode-open-30s-v2.json",
            "shot_schedule": "studio/s01e001/storyboard/shot-schedule.json",
            "pipeline_stages": ["script", "character_specs", "storyboard", "keyframe", "i2v",
                                "edit", "qa", "owner_review"],
            "render_runtime": "remotion-composer (Explainer) / HyperFrames alternatifi",
        },
        "asset_map": {
            "park": "characters/scenes/park-kite-01.json",
            "kite": "studio/canon/continuity-rules.json",
            "tail_six_strips": "studio/canon/continuity-rules.json",
            "reference_keyframe": "deliverables/S01-PARK-KITE-001/keyframes/keyframe-girl-seed-77.png",
            "test_video_5s": "deliverables/S01-PARK-KITE-001/park-kite-take2-girl-1080p.mp4",
        },
        "cost_control": {
            "existing": "OpenMontage tools/cost_tracker.py (budget_total_usd, single_action_approval_usd, cap/warn)",
            "studio_policy": "studio/production/cost-policy.json (0 USD, 12000 token, 300 pending)",
            "live_gate": "ahos_core/ahos/llm_executor.py::_studio_budget_preflight",
            "paid_tools": "require_approval_for_new_paid_tool=true; onaysız ücretli araç yok",
        },
        "minimal_changes": [
            "OpenMontage kodunu değiştirme; mevcut character-animation.yaml kullan.",
            "Karakter girdilerini studio/characters/<id>/ üzerinden okuyan salt-okunur adaptör.",
            "S01E001 açılışını text-card storyboard props'una çevir (karakter görseli yok).",
            "Bütçeyi 0 USD + onay kapılı çalıştır; pipeline budget_default_usd=2.00 değerini override et.",
            "AGPLv3 lisans incelemesi tamamlanmadan ticari dağıtım yok.",
        ],
        "blockers": [
            "Remotion CLI yanıt vermiyor (render yok).",
            "Aden/Kaan v2 görseli yok; 14 karakterde görsel kanon yok.",
            "Hiçbir karakterde sahip onayı yok.",
            "OpenMontage AGPLv3 lisansı ticari kullanım için hukuk incelemesi gerektiriyor.",
        ],
        "first_output_candidate": {
            "kind": "EPISODE-OPEN-30s text-card storyboard animatic",
            "props": "studio/integration/openmontage-props/s01e001-opening-storyboard.json",
            "status": "PROPS_READY_RENDER_BLOCKED",
            "note": "Karakter görseli içermez; onaylı üretim değildir.",
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "openmontage-bridge.json").write_text(json.dumps(bridge, ensure_ascii=False, indent=2) + "\n",
                                                 encoding="utf-8")

    cuts = []
    for index, shot in enumerate(opening["shots"]):
        start = shot["start_seconds"]
        cuts.append({
            "id": f"s01e001-open-{index + 1:02d}",
            "source": "",
            "type": "text_card",
            "in_seconds": start,
            "out_seconds": start + shot["duration_seconds"],
            "text": f"{shot['start_seconds']}–{shot['start_seconds'] + shot['duration_seconds']} sn · {shot['action'].split('.')[0]}",
            "fontSize": 46,
            "color": "#F7F4EC",
            "backgroundColor": "#243A5E",
        })
    props = {
        "theme": "studio-storyboard",
        "status": "PLACEHOLDER_NOT_APPROVED",
        "note": "S01E001 açılış storyboard animatiği; karakter görseli yok, final değil.",
        "cuts": cuts,
    }
    props_dir = OUT / "openmontage-props"
    props_dir.mkdir(parents=True, exist_ok=True)
    (props_dir / "s01e001-opening-storyboard.json").write_text(
        json.dumps(props, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"characters": len(bridge["character_map"]), "cuts": len(cuts),
                      "out": str(OUT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
