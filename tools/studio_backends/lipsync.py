"""AHOS Studio OS - `lipsync` backend v0.1 (word-aligned visemes, zero cost).

    python tools/studio_backends/lipsync.py --plan plan.json --job-dir DIR --evidence EV.json

Consumes the approved voice artifact (kind=voice, sha256, licence) and emits a
schema-valid viseme timeline the animation stage can apply to the mouth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import growth  # noqa: E402
import memory  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FACTORY = ROOT / "tools" / "studio_backends" / "lipsync_factory.py"
APPROVED = {"approved", "own", "public-domain", "public_domain", "gpl", "verified"}
MAX_GAP = 1.0
TAIL_TOLERANCE = 0.6


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cast_ids(plan):
    out = []
    for item in plan.get("cast") or []:
        out.append(item.get("id") if isinstance(item, dict) else str(item))
    return [c for c in out if c]


def resolve_voice(cid, plan):
    for art in plan.get("dependency_artifacts") or []:
        if not isinstance(art, dict):
            continue
        kind = str(art.get("kind") or "").lower()
        raw = str(art.get("path") or art.get("filename") or "")
        art_cast = str(art.get("cast") or art.get("character_id") or "").lower()
        if kind and kind != "voice":
            continue
        if art_cast and art_cast != cid.lower():
            continue
        if not raw.lower().endswith(".wav"):
            continue
        path = Path(raw)
        candidates = [path] if path.is_absolute() else [
            (Path(plan.get("_job_dir", ".")) / raw).resolve(), (ROOT / raw).resolve()]
        found = next((p for p in candidates if p.is_file()), None)
        if found is None:
            return None, "DEPENDENCY_MISSING"
        expected = str(art.get("sha256") or "").lower()
        if len(expected) != 64:
            return None, "SHA_MISSING"
        if sha(found) != expected:
            return None, "SHA_MISMATCH"
        if str(art.get("license_status") or "").lower() not in APPROVED:
            return None, "LICENSE_UNVERIFIED"
        return found, None
    return None, "VOICE_DEPENDENCY_REQUIRED"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--evidence", required=True)
    ns = parser.parse_args(argv)

    job = Path(ns.job_dir).resolve()
    job.mkdir(parents=True, exist_ok=True)
    plan = json.loads(Path(ns.plan).read_text(encoding="utf-8-sig"))
    plan["_job_dir"] = str(job)
    out = job / "lipsync"
    if out.exists():
        for stale in out.iterdir():
            if stale.is_file():
                stale.unlink()
    out.mkdir(parents=True, exist_ok=True)

    coach = growth.guidance("lipsync")
    language = str(plan.get("language") or "tr").lower()
    artifacts, checks, blocked = [], {}, []
    for cid in cast_ids(plan):
        wav, error = resolve_voice(cid, plan)
        if wav is None:
            blocked.append({"component": cid, "code": error,
                            "remediation": "provide the approved voice artifact "
                                           "(kind=voice, sha256, license_status)"})
            continue
        target = out / ("%s-%s-visemes.json" % (cid, language))
        run = subprocess.run([sys.executable, str(FACTORY), "--wav", str(wav),
                              "--out", str(target), "--language", language],
                             capture_output=True, text=True, timeout=900)
        if run.returncode != 0 or not target.is_file():
            blocked.append({"component": cid, "code": "LIPSYNC_FAILED",
                            "remediation": (run.stdout + run.stderr)[-300:].strip()})
            continue
        payload = json.loads(target.read_text(encoding="utf-8"))
        metrics = payload.get("metrics") or {}
        if payload.get("status") != "PASSED" or not metrics.get("viseme_count"):
            blocked.append({"component": cid, "code": "LIPSYNC_EMPTY",
                            "remediation": payload.get("error", "no visemes")})
            continue
        if float(metrics.get("max_gap_seconds") or 0) > MAX_GAP:
            blocked.append({"component": cid, "code": "LIPSYNC_GAP",
                            "remediation": "max_gap %.2fs" % metrics["max_gap_seconds"]})
            continue
        words = payload.get("words") or []
        speech_end = float(words[-1]["end"]) if words else float(payload.get("duration_seconds") or 0)
        tail = max(0.0, speech_end - float(metrics.get("coverage_seconds") or 0))
        if tail > TAIL_TOLERANCE:
            blocked.append({"component": cid, "code": "LIPSYNC_TAIL",
                            "remediation": "speech ends at %.2fs but visemes stop at %.2fs"
                                           % (speech_end, metrics.get("coverage_seconds") or 0)})
            continue

        checks[cid] = {"wav": str(wav), "wav_sha256": sha(wav), "language": language,
                       "words": metrics.get("word_count"),
                       "visemes": metrics.get("viseme_count"),
                       "max_gap_seconds": metrics.get("max_gap_seconds"),
                       "coverage_seconds": metrics.get("coverage_seconds"),
                       "speech_end_seconds": round(speech_end, 3),
                       "tail_after_speech_seconds": round(tail, 3),
                       "method": payload.get("method")}
        artifacts.append({"kind": "lipsync", "cast": cid,
                          "path": str(target.relative_to(job)).replace("\\", "/"),
                          "bytes": target.stat().st_size, "sha256": sha(target)})

    status = "PASSED" if (artifacts and not blocked) else "BLOCKED"
    evidence = {
        "stage": "lipsync", "status": status, "cost_eur": 0,
        "commercial_license_verified": status == "PASSED",
        "license_basis": "faster-whisper (MIT) + heuristic viseme map",
        "cast_ids": cast_ids(plan), "language": language,
        "checks": checks, "artifacts": artifacts, "blocked": blocked,
        "growth": coach, "memory": memory.digest("lipsync"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    memory.remember("lipsync", {"status": status, "cast": cast_ids(plan),
                                "visemes": sum(c.get("visemes") or 0 for c in checks.values()),
                                "blocked_codes": [b.get("code") for b in blocked]})
    evidence["memory_after"] = memory.digest("lipsync")
    Path(ns.evidence).parent.mkdir(parents=True, exist_ok=True)
    Path(ns.evidence).write_text(json.dumps(evidence, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
    print("LIPSYNC_BACKEND_%s cast=%s artifacts=%d blocked=%d"
          % (status, ",".join(cast_ids(plan)), len(artifacts), len(blocked)))
    return 0 if status == "PASSED" else 2


if __name__ == "__main__":
    sys.exit(main())

