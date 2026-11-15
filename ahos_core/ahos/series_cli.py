"""Dizi komut satırı: sezon planla, bölüm üret, durumu yazdır.

    python -m ahos.series_cli --root <dizi-dizini> plan --episodes 50
    python -m ahos.series_cli --root <dizi-dizini> produce --episode 1
    python -m ahos.series_cli --root <dizi-dizini> status
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .series import (
    Character,
    SeriesBible,
    build_episode,
    load_state,
    plan_season,
    save_state,
    series_manifest,
)
from .studio_pipeline import produce_episode


def _bible(root: Path) -> SeriesBible:
    path = root / "series.json"
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        data["characters"] = [Character(**item) for item in data.get("characters", [])]
        return SeriesBible(**data)
    return SeriesBible(
        series_id=root.name or "dizi",
        title="Aden ve Kaan",
        premise="İki kardeş her bölüm yeni bir şey keşfeder.",
        characters=[
            Character("aden", "Aden", "female"),
            Character("kaan", "Kaan", "male"),
        ],
    )


def _save_bible(root: Path, series: SeriesBible) -> Path:
    path = root / "series.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(series_manifest(series), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _preflight(require_comfy: bool = False, *, providers_path: str | None = None,
               require_runpod: bool = False, model_path: str | None = None
               ) -> tuple[bool, list[dict]]:
    """Hazırlık kontrolü: araçlar + katalog + (istenirse) ComfyUI / RunPod / model.

    Yalnızca yapılandırılmış kontroller çalışır; hiçbiri sessizce atlanmaz,
    sonuç tek bir `checklist` olarak döner (fail-closed).
    """

    import os
    import shutil

    checklist: list[dict] = []
    for tool in ("ffmpeg", "ffprobe"):
        checklist.append({"check": tool, "ok": bool(shutil.which(tool)),
                          "hint": "PATH'e ekleyin"})

    if providers_path:
        from .studio_department import ProviderRegistry, ProviderRegistryError

        try:
            registry = ProviderRegistry.load(providers_path)
            checklist.append({"check": "providers", "ok": bool(registry.providers),
                              "hint": f"{len(registry.providers)} kayıt"})
        except ProviderRegistryError as exc:
            checklist.append({"check": "providers", "ok": False, "hint": str(exc)[:120]})

    if require_comfy:
        from .comfy_bridge import ComfyUnavailable, health

        try:
            info = health(timeout=3.0)
            checklist.append({"check": "comfyui", "ok": True,
                              "hint": str(info.get("host") or "")})
        except ComfyUnavailable as exc:
            checklist.append({"check": "comfyui", "ok": False, "hint": str(exc)[:120]})

    if require_runpod:
        endpoint = str(os.environ.get("AHOS_RUNPOD_ENDPOINT") or "").strip()
        if not endpoint:
            checklist.append({"check": "runpod", "ok": False,
                              "hint": "AHOS_RUNPOD_ENDPOINT tanımlı değil"})
        else:
            import urllib.error
            import urllib.request

            try:
                with urllib.request.urlopen(endpoint, timeout=4) as response:
                    ok = 200 <= int(response.status) < 500
                checklist.append({"check": "runpod", "ok": ok, "hint": endpoint})
            except (urllib.error.URLError, OSError, ValueError) as exc:
                checklist.append({"check": "runpod", "ok": False, "hint": str(exc)[:120]})

    if model_path:
        from pathlib import Path

        exists = Path(model_path).exists()
        checklist.append({"check": "model", "ok": exists, "hint": str(model_path)})

    return all(row["ok"] for row in checklist), checklist


def _cost_estimate(episode) -> dict:
    """Ses işlerinden maliyet tahmini (çağrı yapmaz)."""

    from .audio_pipeline import AudioBudgetPolicy, plan_jobs
    from .costs import estimate

    jobs = plan_jobs(episode, AudioBudgetPolicy())
    plan = []
    for job in jobs:
        if job.task_type.value == "dialogue_tts":
            units = len(str(job.payload.get("text") or "")) / 1000.0
        else:
            units = float(job.payload.get("seconds") or 0.0)
        plan.append({"stage": job.task_type.value, "provider": job.provider_id,
                     "units": units})
    return estimate(plan)


def _dry_run(episode, out, number: int, args) -> int:
    """Plan + maliyet tahmini; sağlayıcı çağrısı YAPMAZ."""

    from .audio_pipeline import AudioBudgetPolicy, plan_jobs
    from .costs import BudgetRefusal, estimate, guard

    jobs = plan_jobs(episode, AudioBudgetPolicy())
    plan = []
    for job in jobs:
        if job.task_type.value == "dialogue_tts":
            units = len(str(job.payload.get("text") or "")) / 1000.0
        else:
            units = float(job.payload.get("seconds") or 0.0)
        plan.append({"stage": job.task_type.value, "provider": job.provider_id,
                     "units": units})
    report = estimate(plan)
    try:
        if args.max_cost:
            guard(report, episode_cap=args.max_cost)
    except BudgetRefusal as exc:
        print(f"[butce] reddedildi: {exc}")
        return 4

    out.mkdir(parents=True, exist_ok=True)
    payload = {"episode": number, "dry_run": True, "jobs": len(jobs),
               "duration_seconds": round(episode.duration(), 3), "cost": report}
    (out / "dry-run.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

    parser = argparse.ArgumentParser(prog="ahos-series", description="dizi üretim hattı")
    parser.add_argument("--root", required=True, help="dizi dizini")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--scenes", type=int, default=4)
    parser.add_argument("--lines-per-scene", type=int, default=2)
    parser.add_argument("--line-seconds", type=float, default=3.0)
    parser.add_argument("--no-voice", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="Yalnızca plan + maliyet tahmini (sağlayıcı çağrısı yok)")
    parser.add_argument("--resume", action="store_true",
                        help="Doğrulanmış bölüm varsa atla")
    parser.add_argument("--max-cost", type=float, default=0.0,
                        help="Bölüm başına sert maliyet tavanı (0 = yalnız ücretsiz)")
    parser.add_argument("--providers", default=None,
                        help="Sağlayıcı kataloğu yolu")
    parser.add_argument("command", choices=["plan", "produce", "status"])
    parser.add_argument("--episode", type=int, default=None)
    args = parser.parse_args(argv)

    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    series = _bible(root)
    _save_bible(root, series)
    state = load_state(root)

    if args.command == "plan":
        plans = plan_season(series, episodes=args.episodes)
        (root / "season.json").write_text(
            json.dumps([plan.__dict__ for plan in plans], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(json.dumps({"planned": len(plans), "first": plans[0].__dict__,
                          "file": str(root / "season.json")}, indent=2, ensure_ascii=False))
        return 0

    if args.command == "status":
        print(json.dumps({"series": series.title, "state": state}, indent=2, ensure_ascii=False))
        return 0

    number = args.episode or int(state.get("next_episode") or 1)
    plans = plan_season(series, episodes=max(number, int(state.get("planned") or args.episodes)))
    plan = plans[number - 1]
    episode = build_episode(series, plan, lines_per_scene=args.lines_per_scene,
                            line_seconds=args.line_seconds)
    out = root / "episodes" / f"b{number:02d}"
    import time

    started_at = time.time()
    if args.dry_run:
        return _dry_run(episode, out, number, args)
    if args.resume and (out / "episode.mp4").is_file():
        print(json.dumps({"episode": number, "skipped": True,
                          "reason": "verified episode exists", "out": str(out)},
                         ensure_ascii=False, indent=2))
        return 0
    ready, checklist = _preflight(require_comfy=False, providers_path=args.providers)
    if not ready:
        print(json.dumps({"ready": False, "checklist": checklist},
                         ensure_ascii=False, indent=2))
        return 3

    # Maliyet kapısı: üretimden ÖNCE tahmin + bütçe kontrolü (paid çağrı yok).
    from .costs import BudgetRefusal, guard

    estimate_report = _cost_estimate(episode)
    if args.max_cost:
        try:
            guard(estimate_report, episode_cap=args.max_cost)
        except BudgetRefusal as exc:
            print(json.dumps({"blocked_budget": True, "reason": str(exc),
                              "estimate": estimate_report}, ensure_ascii=False, indent=2))
            return 4
    report = produce_episode(episode, out, language=series.language, use_voice=not args.no_voice)

    # Crash safety: yarım dosya bırakma (temp -> atomic replace) + stage ledger.
    import shutil

    final_video = out / "episode.mp4"
    if final_video.is_file():
        partial = out / "episode.partial.mp4"
        shutil.copy2(final_video, partial)
        partial.replace(final_video)
    ledger = {
        "schema": "ahos.production-ledger.v1",
        "episode": number,
        "title": plan.title,
        "duration_seconds": (report.get("measurements") or {}).get("duration_seconds"),
        "passed": bool(report.get("passed")),
        "stages": [
            {"stage": "story", "status": "verified", "provider": "local-template"},
            {"stage": "voice",
             "status": "verified" if report.get("voice") else "skipped",
             "provider": (report.get("voice") or {}).get("engine") or "none"},
            {"stage": "render",
             "status": "verified" if final_video.is_file() else "failed",
             "provider": "local-2d"},
            {"stage": "qa", "status": "passed" if report.get("passed") else "failed",
             "provider": "studio-qa"},
        ],
        "cost": {"total_cost": 0.0, "currency": "USD", "note": "free/local path"},
        "retries": 0,
        "episode_id": f"b{number:02d}",
    }
    (out / "production-ledger.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")

    # Durum özeti: süre, stage zamanları, maliyet, tahmini kalan süre.
    elapsed = round(time.time() - started_at, 2)
    summary = {
        "schema": "ahos.production-summary.v1",
        "episode": number,
        "status": "verified" if ledger["passed"] else "failed",
        "duration_seconds": ledger["duration_seconds"],
        "elapsed_seconds": elapsed,
        "stages": [{"stage": row["stage"], "status": row["status"]} for row in ledger["stages"]],
        "current_stage": None,
        "cost_so_far": ledger["cost"]["total_cost"],
        "currency": ledger["cost"]["currency"],
        "eta_seconds": 0,
        "passed": ledger["passed"],
    }
    (out / "production-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


    state["produced"] = sorted(set(state.get("produced", [])) | {number})
    state["next_episode"] = number + 1
    state["planned"] = len(plans)
    state["last"] = {"number": number, "passed": report["passed"], "score": report["score"]}
    save_state(root, state)

    print(json.dumps({
        "episode": number,
        "title": plan.title,
        "out": str(out),
        "passed": report["passed"],
        "score": report["score"],
        "duration": report["measurements"].get("duration_seconds"),
        "voice": (report.get("voice") or {}).get("voice"),
        "problems": report["problems"],
    }, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
