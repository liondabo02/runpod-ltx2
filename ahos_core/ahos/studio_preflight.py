from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Mapping, Sequence

from .audio_pipeline import DEFAULT_LANGUAGE_POLICIES
from .runpod_chatterbox import SUPPORTED_LANGUAGES
from .studio_approval import _atomic_write, _read_object


def build_execution_preflight(
    studio_directory: str | Path,
    *,
    ltx2_hourly_usd: float,
    tts_hourly_usd: float,
    render_realtime_factor: float = 8.0,
    tts_realtime_factor: float = 1.0,
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    if min(ltx2_hourly_usd, tts_hourly_usd) < 0:
        raise ValueError("hourly rates must not be negative")
    if render_realtime_factor <= 0 or tts_realtime_factor <= 0:
        raise ValueError("realtime factors must be positive")
    studio = Path(studio_directory)
    approval = _read_object(studio / "OWNER-APPROVAL.json")
    render = _read_object(studio / "artifacts" / "render-jobs.json")
    localization = _read_object(studio / "artifacts" / "localization-plan.json")
    voices = _read_object(studio / "artifacts" / "voice-casting.json")
    env = os.environ if environment is None else environment

    jobs = render.get("jobs")
    units = localization.get("units")
    characters = voices.get("characters")
    if not isinstance(jobs, list) or not isinstance(units, list) or not isinstance(characters, list):
        raise ValueError("studio artifacts have invalid collection fields")

    render_seconds = sum(float(job.get("duration_seconds", 0)) for job in jobs if isinstance(job, Mapping))
    localized = [unit for unit in units if isinstance(unit, Mapping) and str(unit.get("localized_text") or "").strip()]
    missing_translation = len(units) - len(localized)
    # Text duration is conservatively estimated at 13 visible characters/second.
    tts_seconds = sum(max(0.35, len(str(unit.get("localized_text"))) / 13.0) for unit in localized)
    render_gpu_seconds = render_seconds * render_realtime_factor
    tts_gpu_seconds = tts_seconds * tts_realtime_factor
    render_cost = render_gpu_seconds / 3600 * ltx2_hourly_usd
    tts_cost = tts_gpu_seconds / 3600 * tts_hourly_usd
    subtotal = render_cost + tts_cost
    estimate = round(subtotal * 1.20, 6)  # retry/cold-start reserve

    required_languages = {item.code for item in DEFAULT_LANGUAGE_POLICIES if item.required}
    unsupported = sorted(required_languages - set(SUPPORTED_LANGUAGES))
    missing_voice_references = sorted(
        str(item.get("character_id") or "unknown")
        for item in characters
        if isinstance(item, Mapping) and not str(item.get("reference_audio_uri") or "").strip()
    )
    checks = {
        "runpod_api_key_present": bool(str(env.get("RUNPOD_API_KEY", "")).strip()),
        "ltx2_endpoint_present": bool(str(env.get("RUNPOD_LTX2_ENDPOINT_ID", "")).strip()),
        "tts_endpoint_present": bool(str(env.get("RUNPOD_CHATTERBOX_ENDPOINT_ID", "")).strip()),
        "rates_configured": ltx2_hourly_usd > 0 and tts_hourly_usd > 0,
        "translations_complete": missing_translation == 0,
        "required_languages_supported": not unsupported,
        "canonical_voice_references_ready": not missing_voice_references,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    payload: dict[str, object] = {
        "schema": "ahos.production-execution-preflight.v1",
        "episode_id": approval.get("episode_id"),
        "approval_ready": not blockers,
        "checks": checks,
        "blockers": blockers,
        "details": {
            "render_jobs": len(jobs),
            "render_output_seconds": round(render_seconds, 3),
            "localization_units": len(units),
            "missing_translation_units": missing_translation,
            "unsupported_tts_languages": unsupported,
            "missing_voice_reference_characters": missing_voice_references,
        },
        "cost_estimate": {
            "currency": "USD",
            "render_hourly_rate": ltx2_hourly_usd,
            "tts_hourly_rate": tts_hourly_usd,
            "render_gpu_seconds": round(render_gpu_seconds, 3),
            "tts_gpu_seconds": round(tts_gpu_seconds, 3),
            "subtotal": round(subtotal, 6),
            "retry_and_cold_start_reserve_percent": 20,
            "recommended_budget_ceiling": estimate,
            "estimate_is_binding": False,
        },
        "external_calls_made": False,
    }
    _atomic_write(studio / "EXECUTION-PREFLIGHT.json", payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check studio execution readiness and estimate cost")
    parser.add_argument("--studio-dir", required=True)
    parser.add_argument("--ltx2-hourly-usd", type=float, required=True)
    parser.add_argument("--tts-hourly-usd", type=float, required=True)
    parser.add_argument("--render-realtime-factor", type=float, default=8.0)
    parser.add_argument("--tts-realtime-factor", type=float, default=1.0)
    args = parser.parse_args(argv)
    result = build_execution_preflight(
        args.studio_dir,
        ltx2_hourly_usd=args.ltx2_hourly_usd,
        tts_hourly_usd=args.tts_hourly_usd,
        render_realtime_factor=args.render_realtime_factor,
        tts_realtime_factor=args.tts_realtime_factor,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["approval_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
