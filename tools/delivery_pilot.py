"""AHOS-DELIVERY-001 — gerçek pilot video üretimi (deterministik hat).

Üretir: MP4 + poster + TR/DE SRT + script + manifest (SHA-256, ffprobe, QA).
QA geçmezse `delivery.verified=false` ve çıkış kodu 1.

Kullanım:
    python tools/delivery_pilot.py --seconds 5 --out deliverables/ADEN-PILOT-001
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
sys.path.insert(0, str(CORE))

from ahos import media_delivery as md  # noqa: E402
from ahos import project_run  # noqa: E402

SCRIPT_TR = ("Aden ve Kaan uçurtma uçuruyordu. Rüzgâr kuyruğu kopardı; "
             "birlikte yeni bir kuyruk yaptılar.")
SCRIPT_5S = "Aden ve Kaan uçurtma uçuruyordu."
SCRIPT_PILOT = ("Bir bahar sabahı Aden ve Kaan uçurtma uçurmaya çıktı. "
                "Rüzgâr tatlı tatlı esiyordu. Uçurtma gökyüzünde dans ediyordu. "
                "Derken sert bir rüzgâr geldi ve uçurtmanın kuyruğu koptu. "
                "Aden üzüldü. Kaan, birlikte yeni bir kuyruk yaparız, dedi. "
                "İki kardeş renkli kumaşlar buldu. Sabırla düğümlediler. "
                "Yeni kuyruk rengârenk oldu. Uçurtma yeniden yükseldi. "
                "Birlikte başardılar.")
SCRIPT_PILOT_DE = ("An einem Frühlingsmorgen gingen Aden und Kaan drachensteigen. "
                   "Der Wind wehte sanft, der Drachen tanzte am Himmel. "
                   "Dann kam ein starker Windstoß und der Drachenschwanz riss ab. "
                   "Aden war traurig. Kaan sagte: Wir bauen gemeinsam einen neuen. "
                   "Die Geschwister fanden bunte Stoffe und knoteten sie geduldig "
                   "zusammen. Der neue Schwanz wurde bunt. Der Drachen stieg wieder "
                   "auf. Gemeinsam haben sie es geschafft.")
CUES_TR = ["Bir bahar sabahı Aden ve Kaan uçurtma uçurmaya çıktı.",
           "Sert rüzgâr kuyruğu kopardı; Kaan 'birlikte yaparız' dedi.",
           "Renkli kumaşlarla yeni kuyruk dikildi; uçurtma yeniden yükseldi."]
CUES_DE = ["An einem Frühlingsmorgen gingen Aden und Kaan drachensteigen.",
           "Ein starker Wind riss den Schwanz ab; Kaan sagte: Wir schaffen das gemeinsam.",
           "Aus bunten Stoffen wurde ein neuer Schwanz; der Drachen stieg wieder auf."]


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def build(*, seconds: float, out_dir: Path, width: int = 1920,
          height: int = 1080, fps: int = 24, text: str = SCRIPT_5S,
          project_id: str = "ADEN-PILOT-001", narration: str | None = None,
          german: bool = False, cues_tr: list[str] | None = None,
          cues_de: list[str] | None = None) -> dict:
    narration = narration or text
    out = out_dir
    out.mkdir(parents=True, exist_ok=True)
    runtime = ROOT / "ahos_core" / "runtime"

    # G004/G005/G010 — gerçek görev öncesi plan, belirsizlik ve uzman seçimi
    preflight: dict = {"routing": {}}
    try:
        from ahos import cognitive_memory as cm
        from ahos import expert_router

        profile = cm.load(runtime, "creative-manager", "creative")
        preflight["assessment"] = cm.assess_task(profile, task="pilot video üretimi")
        plans = cm.build_plans(profile, goal="Aden pilot videosunu üret", candidates=[
            {"name": "deterministik_yerel", "steps": ["senaryo", "kare", "ses", "mux"],
             "risk": 0.1, "success_probability": 0.95, "estimated_cost_usd": 0.0,
             "verification": "bağımsız QA", "evidence_score": 0.9},
            {"name": "runpod_ltx2", "steps": ["GPU kirala", "LTX-2 render"],
             "risk": 0.55, "success_probability": 0.55, "estimated_cost_usd": 0.8,
             "verification": "ffprobe + QA", "evidence_score": 0.4},
            {"name": "hibrit", "steps": ["yerel kare", "bulut ses"],
             "risk": 0.3, "success_probability": 0.8, "estimated_cost_usd": 0.2,
             "verification": "QA", "evidence_score": 0.6},
        ])
        preflight["plan"] = {"chosen": plans["chosen"], "rationale": plans["rationale"]}
        for task_id, skills in (("script", ["story", "screenplay", "senaryo"]),
                                ("frames", ["animation", "art", "visual"]),
                                ("audio", ["audio", "sound", "ses"]),
                                ("mux", ["python", "software", "code"])):
            result = expert_router.route(runtime, skills)
            preflight["routing"][task_id] = {
                "selected": (result.get("selected") or {}).get("worker"),
                "department": (result.get("selected") or {}).get("department"),
                "reason": result.get("rationale")}
    except (OSError, ValueError, KeyError) as exc:  # pragma: no cover - kayıt yoksa
        preflight["error"] = f"{type(exc).__name__}: {exc}"

    def _worker(task_id: str, default: str) -> str:
        selected = (preflight.get("routing", {}).get(task_id) or {}).get("selected")
        return selected or default

    frames_dir = out / "frames"
    state: dict[str, dict] = {}

    def executor(task):
        task_id = task["task_id"]
        if task_id == "script":
            path = _write(out / "script-tr.txt", narration + "\n")
            state["script"] = {"path": str(path)}
            return {"ok": True, "output": str(path), "evidence": "script-tr.txt",
                    "worker": task["worker"]}
        if task_id == "frames":
            info = md.render_frames(frames_dir, seconds=seconds, fps=fps,
                                    width=width, height=height)
            state["frames"] = info
            return {"ok": info["frames"] > 0, "output": info["dir"],
                    "evidence": f"{info['frames']} PNG kare", "worker": task["worker"]}
        if task_id == "audio":
            mp3 = out / "narration-tr.mp3"
            md.synthesize(narration, mp3)
            wav = out / "audio-tr.wav"
            md.build_audio(mp3, wav, seconds=seconds)
            state["audio"] = {"mp3": str(mp3), "wav": str(wav)}
            return {"ok": wav.is_file(), "output": str(wav),
                    "evidence": "narration-tr.mp3 + audio-tr.wav",
                    "worker": task["worker"]}
        if task_id == "mux":
            video = out / "aden-pilot.mp4"
            md.mux(frames_dir, out / "audio-tr.wav", video, fps=fps, seconds=seconds)
            state["video"] = str(video)
            return {"ok": video.is_file() and video.stat().st_size > 0,
                    "output": str(video), "evidence": "aden-pilot.mp4",
                    "worker": task["worker"]}
        return {"ok": False, "output": "", "reason": "unknown task"}

    def qa(task, result):
        output = Path(str(result.get("output") or ""))
        exists = output.exists()
        size = output.stat().st_size if exists and output.is_file() else 0
        return {"ok": bool(result.get("ok") and exists and (output.is_dir() or size > 0)),
                "verifier": "qa-01", "note": f"varlık kontrolü; boyut={size}"}

    tasks = [
        {"task_id": "script", "department": "creative",
         "objective": "senaryo ve anlatım metni",
         "worker": _worker("script", "creative-story-lead")},
        {"task_id": "frames", "department": "creative",
         "objective": "sahne kareleri",
         "worker": _worker("frames", "creative-animation-lead"),
         "depends_on": ["script"]},
        {"task_id": "audio", "department": "creative",
         "objective": "Türkçe anlatım ve ses",
         "worker": _worker("audio", "creative-audio-lead"),
         "depends_on": ["script"]},
        {"task_id": "mux", "department": "software",
         "objective": "video birleştirme",
         "worker": _worker("mux", "software-engineering-lead"),
         "depends_on": ["frames", "audio"]},
    ]
    project = project_run.run_project(ROOT / "ahos_core" / "runtime",
                                      project_id=project_id, manager="creative-manager",
                                      tasks=tasks, executor=executor, qa=qa)
    video = out / "aden-pilot.mp4"
    verification = md.verify_video(video, seconds=seconds, fps=fps,
                                   width=width, height=height)
    poster = out / "poster.png"
    frame = md.render_frame(int(seconds * fps * 0.35), int(seconds * fps), width, height)
    frame.save(poster)

    def _rows(cues: list[str] | None, fallback: str) -> list[tuple[float, float, str]]:
        span = max(1.0, seconds - 0.5)
        if not cues:
            return [(0.25, 0.25 + span, fallback)]
        step = span / len(cues)
        return [(0.25 + index * step, 0.25 + (index + 1) * step, cue)
                for index, cue in enumerate(cues)]

    srt_tr = _write(out / "subtitles-tr.srt", md.srt(_rows(cues_tr, text)))
    srt_de = _write(out / "subtitles-de.srt",
                    md.srt(_rows(cues_de, "Aden und Kaan bauen gemeinsam einen neuen Drachen.")))
    german_files = {}
    if german:
        de_mp3 = out / "narration-de.mp3"
        md.synthesize(SCRIPT_PILOT_DE, de_mp3, "de-DE-KatjaNeural")
        de_wav = out / "audio-de.wav"
        md.build_audio(de_mp3, de_wav, seconds=seconds)
        de_video = out / "aden-pilot-de.mp4"
        md.mux(frames_dir, de_wav, de_video, fps=fps, seconds=seconds)
        german_files = {"video": de_video, "audio": de_wav,
                  "qa": md.verify_video(de_video, seconds=seconds, fps=fps,
                                        width=width, height=height)}
    probe = md.probe(video) if video.is_file() else {}
    streams = [{k: s.get(k) for k in ("codec_type", "codec_name", "width", "height",
                                      "avg_frame_rate", "sample_rate", "channels")}
               for s in (probe.get("streams") or [])]
    contributors = [
        {"worker": task.get("worker"), "department": task.get("department"),
         "task": row["task_id"], "output": row.get("output"),
         "verified_by": row.get("verifier"), "status": row["status"]}
        for task, row in zip(tasks, project["tasks"])]
    manifest = {
        "schema": "ahos.delivery.manifest.v1",
        "delivery_id": project_id,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "project": {"manager": project["manager"], "state": str(
            ROOT / "ahos_core" / "runtime" / "projects" / project_id / "state.json")},
        "spec": {"seconds": seconds, "fps": fps, "width": width, "height": height,
                 "script": text},
        "files": {
            "video": {"path": str(video), "exists": video.is_file(),
                      "bytes": video.stat().st_size if video.is_file() else 0,
                      "sha256": md.sha256(video) if video.is_file() else ""},
            "poster": {"path": str(poster), "sha256": md.sha256(poster)},
            "subtitles_tr": {"path": str(srt_tr), "sha256": md.sha256(srt_tr)},
            "subtitles_de": {"path": str(srt_de), "sha256": md.sha256(srt_de)},
            "audio": {"path": str(out / "audio-tr.wav"),
                      "sha256": md.sha256(out / "audio-tr.wav")
                      if (out / "audio-tr.wav").is_file() else ""},
        },
        "ffprobe": {"format": (probe.get("format") or {}), "streams": streams},
        "qa": {"verifier": "qa-01", "independent": True,
               "ok": verification["ok"], "checks": verification["checks"]},
        "preflight": preflight,
        "files_de": ({"video": str(german_files["video"]),
                      "sha256": md.sha256(german_files["video"]),
                      "qa_ok": german_files["qa"]["ok"]} if german_files else {}),
        "contributors": contributors,
        "cost_usd": 0.0,
        "reproduce": "python tools/delivery_pilot.py --seconds %s --out %s" % (
            seconds, out.as_posix()),
        "delivery": {
            "processed": bool(project["summary"]["completed"] == len(tasks)),
            "file_created": video.is_file() and video.stat().st_size > 0,
            "file_verified": verification["ok"],
            "qa_passed": verification["ok"],
            "delivered": verification["ok"],
        },
        "note": ("Deterministik vektörel hat; LTX-2/ComfyUI modeli kullanılmadı. "
                 "Kareler PIL ile çizildi, ses edge-tts ile üretildi, mux ffmpeg."),
    }
    md.write_manifest(out / "manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--out", default="deliverables/ADEN-PILOT-001")
    parser.add_argument("--text", default=SCRIPT_5S)
    parser.add_argument("--project-id", default="ADEN-PILOT-001")
    parser.add_argument("--pilot", action="store_true",
                        help="30-45 sn pilot: 3 sahne, tam anlatım, Almanca sürüm")
    parser.add_argument("--german", action="store_true")
    args = parser.parse_args()
    out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
    text = SCRIPT_PILOT if args.pilot else args.text
    manifest = build(seconds=max(1.0, args.seconds), out_dir=out,
                     text=text, narration=text, project_id=args.project_id,
                     german=args.german or args.pilot,
                     cues_tr=CUES_TR if args.pilot else None,
                     cues_de=CUES_DE if args.pilot else None)
    print(json.dumps({"delivered": manifest["delivery"]["delivered"],
                      "video": manifest["files"]["video"],
                      "qa_ok": manifest["qa"]["ok"],
                      "manifest": str(out / "manifest.json")}, ensure_ascii=False))
    return 0 if manifest["delivery"]["delivered"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
