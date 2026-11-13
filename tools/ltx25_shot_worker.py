"""AHOS LTX-2.5 shot worker: real local pipeline adapter, fail-closed.

Does not download weights, start/allocate GPUs, or pretend a dummy graph is video.
Use only with an already-authorized worker and officially supported LTX-2.5 models.
This file is not registered as an AHOS production backend until an actual GPU
render and independent creative QA are demonstrated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MODELS = (
    "diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors",
    "text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors",
    "vae/ltx-2.5-video-vae-bf16.safetensors",
    "vae/ltx-2.5-audio-vae-bf16.safetensors",
    "latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors",
)

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def root_file(root: Path, rel: str) -> Path:
    if not isinstance(rel, str) or not rel.strip():
        raise ValueError("Missing relative file path")
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError("Path traversal or absolute path rejected")
    result = (root / p).resolve()
    if root.resolve() not in result.parents:
        raise ValueError("File must stay inside the AHOS repository")
    if not result.is_file():
        raise ValueError("Required source file not found: " + rel)
    return result

def load_shot(plan_path: Path, root: Path = ROOT) -> tuple[dict, Path]:
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    if data.get("schema") != "ahos.studio.ltx25.shot.v1":
        raise ValueError("Only verified LTX-2.5 shot schema is accepted")
    prompt = data.get("shot_prompt")
    if not isinstance(prompt, str) or not (50 <= len(prompt) <= 4000):
        raise ValueError("Need a detailed 50-4000 character shot prompt")
    if data.get("model") != "ltx-2.5":
        raise ValueError("Model/version mismatch")
    if data.get("license_status") != "SOURCE_RIGHTS_REVIEWED":
        raise ValueError("Scene input rights have not been reviewed")
    image = data.get("reference_frame")
    if not isinstance(image, dict):
        raise ValueError("A locked source frame is mandatory for identity continuity")
    path = root_file(root, image.get("path", ""))
    if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        raise ValueError("Reference frame must be an image")
    expected = image.get("sha256")
    if not isinstance(expected, str) or len(expected) != 64 or expected.lower() != digest(path):
        raise ValueError("Reference-frame identity/hash mismatch")
    fps = data.get("fps", 24)
    frames = data.get("frames", 121)
    width = data.get("width", 1280)
    height = data.get("height", 720)
    if fps != 24 or not isinstance(frames, int) or not (9 <= frames <= 481) or (frames - 1) % 8:
        raise ValueError("FPS must be 24; frame count must be 1+multiple of 8")
    if (width, height) not in ((1280, 720), (1920, 1080)):
        raise ValueError("Unsupported canary resolution")
    return data, path

def preflight(config: dict, plan: dict, reference: Path) -> dict:
    """Check assets and installed runtime without making any paid calls."""
    repo = Path(config.get("ltx_repo", "")).expanduser()
    models = Path(config.get("model_dir", "")).expanduser()
    missing = []
    if not repo.is_dir() or not (repo / "ltx_pipelines").is_dir():
        missing.append("LTX-2 Python pipelines source not installed")
    if not models.is_dir():
        missing.append("LTX-2.5 models directory unavailable")
    else:
        missing += ["model component missing: " + part for part in REQUIRED_MODELS
                    if not (models / part).is_file()]
    if shutil.which("uv") is None:
        missing.append("uv executable not installed")
    if shutil.which("ffprobe") is None:
        missing.append("ffprobe executable not installed")
    if not reference.is_file():
        missing.append("Approved shot reference missing")
    if config.get("provider") != "existing-owned-gpu":
        missing.append("Provider must be an existing authorized GPU resource")
    if config.get("new_spend_limit_eur") != 0:
        missing.append("New spending is not permitted")
    if config.get("license_terms_accepted") is not True:
        missing.append("LTX-2.x license terms must be reviewed and accepted")
    return {"ready_for_execution":not missing,"missing":missing,
            "model_family":"LTX-2.5","workflow":"official distilled Python pipeline",
            "new_spending_authorized":False,
            "professional_quality_verified":False}

def media_proof(path: Path) -> dict:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe is required")
    run = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries",
         "stream=codec_type,width,height,r_frame_rate:format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, timeout=30, check=True)
    meta = json.loads(run.stdout)
    streams = meta.get("streams", [])
    videos = [s for s in streams if s.get("codec_type") == "video"]
    audios = [s for s in streams if s.get("codec_type") == "audio"]
    duration = float(meta.get("format", {}).get("duration", 0))
    if not videos or not audios or duration < 1:
        raise RuntimeError("Real nontrivial video + audio is required")
    if videos[0].get("width", 0) < 1280 or videos[0].get("height", 0) < 720:
        raise RuntimeError("Video below canary quality threshold")
    if path.stat().st_size < 100000:
        raise RuntimeError("Suspiciously small video; inspect source")
    return {"duration":duration,"width":videos[0]["width"],
            "height":videos[0]["height"],"has_audio":True,
            "size_bytes":path.stat().st_size,"sha256":digest(path)}

def execute(plan: dict, reference: Path, config: dict, job_dir: Path,
            *, permitted: bool) -> dict:
    check = preflight(config, plan, reference)
    if not check["ready_for_execution"]:
        raise RuntimeError("LTX-2.5 preflight failed: " + "; ".join(check["missing"]))
    if not permitted or os.environ.get("AHOS_EXISTING_GPU_AUTHORIZED") != "1":
        raise RuntimeError("Explicit authorization for EXISTING GPU allocation is required")
    out = job_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    repo = Path(config["ltx_repo"]).expanduser().resolve()
    models = Path(config["model_dir"]).expanduser().resolve()
    result = out / "ltx25-canary.mp4"
    cmd = [
        "uv", "run", "--no-sync", "python", "-m", "ltx_pipelines.distilled",
        "--transformer-path", str(models / REQUIRED_MODELS[0]),
        "--text-encoder-path", str(models / REQUIRED_MODELS[1]),
        "--video-vae-path", str(models / REQUIRED_MODELS[2]),
        "--audio-vae-path", str(models / REQUIRED_MODELS[3]),
        "--spatial-upsampler-path", str(models / REQUIRED_MODELS[4]),
        "--num-frames", str(plan["frames"]), "--width", str(plan["width"]),
        "--height", str(plan["height"]),
        "--seed", str(plan.get("seed", 42)), "--prompt", plan["shot_prompt"],
        "--image", str(reference), "0", "0.8",
        "--output-path", str(result),
    ]
    # No shell, model auto-download, provider provisioning or API invocation.
    timeout = int(config.get("max_render_seconds", 1800))
    if not 60 <= timeout <= 14400:
        raise ValueError("Unsafe render-time budget")
    run = subprocess.run(cmd, cwd=repo, capture_output=True, text=True,
                         timeout=timeout, check=False)
    if run.returncode != 0:
        raise RuntimeError("LTX-2.5 worker returned exit " + str(run.returncode)
                           + ": " + run.stderr[-500:])
    if not result.is_file():
        raise RuntimeError("Model reported success but created no video")
    proof = media_proof(result)
    return {"schema":"ahos.studio.ltx25.evidence.v1",
            "stage":"render","status":"TECHNICAL_CANDIDATE_NOT_APPROVED",
            "output":str(result),"media_proof":proof,
            "reference_sha256":digest(reference),
            "quality_route":"identity -> motion -> sound -> lighting -> creative QA",
            "source_license_reviewed":True,
            "output_identity_approved":False,
            "commercial_release_approved":False,
            "production_ready":False,"new_paid_api_calls":0}

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--job-dir", type=Path, required=True)
    ap.add_argument("--evidence", type=Path)
    ap.add_argument("--mode", choices=("preflight","render"), default="preflight")
    ap.add_argument("--authorize-existing-gpu", action="store_true")
    args = ap.parse_args(argv)
    plan, source = load_shot(args.plan)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if args.mode == "preflight":
        result = preflight(config, plan, source)
    else:
        result = execute(plan, source, config, args.job_dir,
                         permitted=args.authorize_existing_gpu)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if (args.mode=="render" or result["ready_for_execution"]) else 2

if __name__ == "__main__":
    raise SystemExit(main())
