"""Evidence-based roadmap and episode readiness reporting.

The score in this module is deliberately a *capability evidence score*, not an
estimate of time remaining.  Each roadmap item receives its published point
weight only when both its implementation module and its focused test file are
present.  Operational/release readiness is reported separately and never
inferred from source-code presence.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


@dataclass(frozen=True)
class Capability:
    capability_id: str
    department: str
    title: str
    weight: int
    module: str
    test: str


# Stable, reviewable 100-point roadmap. Points express product importance, not
# engineering hours. Changing this rubric requires a schema/version change.
CAPABILITIES = (
    Capability("story", "story", "AI story planning and validation", 10, "autonomous_story_room.py", "test_autonomous_story_room.py"),
    Capability("continuity", "continuity", "Character and story continuity", 8, "character_memory.py", "test_character_memory.py"),
    Capability("localization", "localization", "Seven-language localization QA", 10, "autonomous_localization.py", "test_autonomous_localization.py"),
    Capability("voice", "voice", "Voice casting and Kurmanji TTS gates", 10, "kurmanji_tts.py", "test_kurmanji_tts.py"),
    Capability("visual", "art_and_animation", "Visual and render-job pipeline", 12, "visual_pipeline.py", "test_visual_pipeline.py"),
    Capability("assembly", "postproduction", "Verified media assembly", 10, "media_assembly.py", "test_media_assembly.py"),
    Capability("governance", "owner_control", "Tamper-evident owner approval", 10, "studio_approval.py", "test_studio_approval.py"),
    Capability("preflight", "operations", "Cost and execution preflight", 8, "studio_preflight.py", "test_studio_preflight.py"),
    Capability("delivery", "publishing", "Episode delivery gate", 10, "episode_delivery.py", "test_episode_delivery.py"),
    Capability("coding_worker", "engineering", "Isolated coding worker", 6, "coding_worker.py", "test_coding_worker.py"),
    Capability("coding_supervisor", "engineering", "Persistent coding backlog supervisor", 6, "coding_supervisor.py", "test_coding_supervisor.py"),
)


def _object(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _project_root(path: str | Path) -> Path:
    root = Path(path).resolve()
    if (root / "ahos").is_dir() and (root / "tests").is_dir():
        return root
    if (root / "ahos_core" / "ahos").is_dir():
        return root / "ahos_core"
    raise ValueError(f"cannot find ahos/ and tests/ below {root}")


def build_readiness_report(
    project_directory: str | Path,
    *,
    studio_directory: str | Path | None = None,
) -> dict[str, object]:
    project = _project_root(project_directory)
    rows: list[dict[str, object]] = []
    earned = 0
    for item in CAPABILITIES:
        module = project / "ahos" / item.module
        test = project / "tests" / item.test
        evidence = {"implementation": module.is_file(), "focused_tests": test.is_file()}
        evidenced = all(evidence.values())
        points = item.weight if evidenced else 0
        earned += points
        rows.append({
            "capability_id": item.capability_id,
            "department": item.department,
            "title": item.title,
            "status": "evidenced" if evidenced else "missing_evidence",
            "weight": item.weight,
            "earned": points,
            "evidence": evidence,
            "missing": [name for name, present in evidence.items() if not present],
        })

    episode: dict[str, object] = {
        "supplied": studio_directory is not None,
        "release_ready": False,
        "checks": {},
        "blockers": ["studio_directory_not_supplied"],
        "departments": [],
    }
    if studio_directory is not None:
        studio = Path(studio_directory).resolve()
        approval = _object(studio / "OWNER-APPROVAL.json")
        preflight = _object(studio / "EXECUTION-PREFLIGHT.json")
        studio_report = _object(studio / "studio-report.json")
        artifacts = studio / "artifacts"
        required_artifacts = (
            "episode.json", "continuity-clearance.json", "production-graph.json",
            "render-jobs.json", "voice-casting.json", "localization-plan.json",
        )
        media = [p for p in artifacts.rglob("*") if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}] if artifacts.is_dir() else []
        checks = {
            "owner_packet": approval is not None,
            "planning_artifacts": all((artifacts / name).is_file() for name in required_artifacts),
            "execution_preflight_passed": bool(preflight and preflight.get("approval_ready") is True),
            "owner_approved": bool(approval and approval.get("owner_approved") is True),
            "paid_execution_enabled": bool(approval and approval.get("paid_execution_enabled") is True),
            "rendered_episode_media": bool(media),
            "release_report_ready": bool(studio_report and studio_report.get("release_ready") is True),
        }
        blockers = [name for name, passed in checks.items() if not passed]
        departments = []
        evidence = approval.get("evidence") if approval else None
        if isinstance(evidence, Mapping) and isinstance(evidence.get("department_statuses"), list):
            departments = evidence["department_statuses"]
        episode = {
            "supplied": True,
            "studio_directory": str(studio),
            "episode_id": approval.get("episode_id") if approval else None,
            "release_ready": not blockers,
            "checks": checks,
            "blockers": blockers,
            "departments": departments,
            "rendered_media": [str(path.relative_to(studio)) for path in media],
        }

    return {
        "schema": "ahos.studio-readiness.v1",
        "score_definition": {
            "name": "capability_evidence_score",
            "earned": earned,
            "possible": sum(item.weight for item in CAPABILITIES),
            "meaning": "Implemented roadmap coverage evidenced by a module and focused tests; not elapsed-time or release completion.",
            "weighting": "Published product-importance points; awarded all-or-nothing per capability.",
        },
        "capabilities": rows,
        "episode": episode,
    }


def human_summary(report: Mapping[str, object]) -> str:
    score = report["score_definition"]
    episode = report["episode"]
    assert isinstance(score, Mapping) and isinstance(episode, Mapping)
    lines = [
        f"Capability evidence: {score['earned']}/{score['possible']} points",
        "This is roadmap evidence, not a time estimate or release percentage.",
    ]
    capabilities = report.get("capabilities", [])
    if isinstance(capabilities, list):
        missing = [row for row in capabilities if isinstance(row, Mapping) and row.get("status") != "evidenced"]
        lines.append(f"Capability gaps: {len(missing)}")
        lines.extend(f"  - {row['department']}: {row['title']}" for row in missing)
    if not episode.get("supplied"):
        lines.append("Episode readiness: not evaluated (use --studio-dir).")
    else:
        lines.append(f"Episode release ready: {'YES' if episode.get('release_ready') else 'NO'}")
        blockers = episode.get("blockers", [])
        if isinstance(blockers, list):
            lines.extend(f"  - blocker: {item}" for item in blockers)
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show evidence-based studio progress and release blockers")
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--studio-dir")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--output", help="also write the JSON report to this path")
    args = parser.parse_args(argv)
    report = build_readiness_report(args.project_dir, studio_directory=args.studio_dir)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.as_json else human_summary(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
