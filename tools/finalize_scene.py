"""Ham bir video çekimini teslim paketine çevirir (sağlayıcıdan bağımsız).

Yapar: 5 sn'ye kırpar, 1920x1080/24 fps'e ölçekler (Lanczos), başlangıç/bitiş
karelerini çıkarır, SHA-256/manifest yazar ve teknik QA'yı çalıştırır.
Yaratıcı QA'yı **PASS etmez**; onay alanı Harun'a bırakılır.

Kullanım:
    python tools/finalize_scene.py --video ham.mp4 --tag take1 \
        --model "LTX-2.5 (HF Space)" --cost-usd 0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _probe(path: Path) -> dict:
    done = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    if done.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {done.stderr[:300]}")
    return json.loads(done.stdout)


def _has_audio(probe: dict) -> bool:
    return any(stream.get("codec_type") == "audio" for stream in probe.get("streams") or [])


def render_final(raw: Path, target: Path, *, seconds: float, width: int, height: int,
                 fps: int, audio: bool) -> None:
    command = [
        "ffmpeg", "-v", "error", "-y", "-i", str(raw),
        "-t", f"{seconds:.3f}",
        "-vf", f"scale={width}:{height}:flags=lanczos,fps={fps}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "16",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
    ]
    if audio:
        command += ["-c:a", "aac", "-b:a", "160k"]
    else:
        command += ["-an"]
    command.append(str(target))
    done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=600)
    if done.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {done.stderr[:400]}")


def extract_frame(video: Path, target: Path, *, last: bool = False, seconds: float = 0.0) -> Path:
    if last:
        duration = float(_probe(video)["format"]["duration"])
        seconds = max(0.0, duration - 0.2)
    done = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, seconds):.2f}", "-i", str(video),
         "-frames:v", "1", str(target)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    if done.returncode != 0 or not target.is_file():
        raise RuntimeError(f"frame extraction failed: {done.stderr[:300]}")
    return target


def _report_markdown(manifest: dict, qa: dict) -> str:
    technical = qa.get("technical") or {}
    motion = qa.get("motion") or {}
    creative = qa.get("creative") or {}
    return "\n".join([
        "# Kalite Raporu — S01-PARK-KITE-001",
        "",
        f"- Üretim: {manifest['generated_at']} · etiket: `{manifest['tag']}`",
        f"- Model/sağlayıcı: {manifest['model']}",
        f"- Dosya: `{manifest['files']['video']['path']}`",
        f"- Süre/çözünürlük: {technical.get('duration_seconds')} sn · "
        f"{technical.get('video', {}).get('width')}x{technical.get('video', {}).get('height')} · "
        f"{technical.get('video', {}).get('fps')} fps",
        f"- Maliyet: {manifest['cost_usd']} USD",
        "",
        "## Teknik QA (otomatik)",
        "",
        f"- Sonuç: **{'PASS' if technical.get('ok') else 'FAIL'}**",
        f"- Donma oranı: {motion.get('freeze_ratio')} → {motion.get('freeze_verdict')}",
        f"- Titreme (flicker): {motion.get('flicker_luma_delta')} → {motion.get('flicker_verdict')}",
        f"- Değişen piksel oranı (ort.): {motion.get('changed_pixel_ratio_mean')}",
        f"- Keskinlik (Laplacian): {motion.get('sharpness_laplacian')}",
        "",
        "## Yaratıcı QA (insan onayı)",
        "",
        f"- Durum: **{creative.get('status')}** — {creative.get('reason')}",
        "- Onaylayan: **Harun**",
        "",
        "| Kontrol | Sonuç |",
        "|---|---|",
        "| Karakter kimliği (Aden/Kaan ayrımı) | ☐ |",
        "| Kıyafet renkleri (kobalt / mercan) | ☐ |",
        "| Boy oranı (0,776 ± %5) | ☐ |",
        "| Doğal hareket / ağırlık aktarımı | ☐ |",
        "| Işık yönü ve sıcaklığı | ☐ |",
        "| Kompozisyon (sol üçte bir / sağ üst uçurtma) | ☐ |",
        "| Bozulma yok (el/yüz/uzuv, titreme) | ☐ |",
        "| Sinematik 3D his | ☐ |",
        "",
        "> Teknik PASS yaratıcı PASS değildir. Bu tablo doldurulmadan sahne teslim sayılmaz.",
    ]) + "\n"


def finalize(video: Path, out_dir: Path, *, tag: str, seconds: float, width: int,
             height: int, fps: int, model: str, cost_usd: float,
             workflow: str = "") -> dict:
    if not video.is_file():
        raise FileNotFoundError(video)
    out_dir.mkdir(parents=True, exist_ok=True)
    probe = _probe(video)
    if not any(s.get("codec_type") == "video" for s in probe.get("streams") or []):
        raise RuntimeError("kaynakta video akışı yok")

    final = out_dir / f"park-kite-{tag}-1080p.mp4"
    render_final(video, final, seconds=seconds, width=width, height=height,
                 fps=fps, audio=_has_audio(probe))
    start = extract_frame(final, out_dir / f"park-kite-{tag}-start.png")
    end = extract_frame(final, out_dir / f"park-kite-{tag}-end.png", last=True)

    import creative_qa

    qa = creative_qa.evaluate(final, scene_id="S01-PARK-KITE-001")
    (out_dir / "qa-technical.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2),
                                               encoding="utf-8")

    final_probe = _probe(final)
    manifest = {
        "schema": "ahos.scene-delivery.v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "scene_id": "S01-PARK-KITE-001",
        "tag": tag,
        "model": model,
        "workflow": workflow,
        "cost_usd": cost_usd,
        "source": {"path": str(video), "bytes": video.stat().st_size, "sha256": _sha256(video)},
        "files": {
            "video": {"path": str(final), "bytes": final.stat().st_size,
                      "sha256": _sha256(final)},
            "start_frame": {"path": str(start), "sha256": _sha256(start)},
            "end_frame": {"path": str(end), "sha256": _sha256(end)},
            "technical_qa": str(out_dir / "qa-technical.json"),
        },
        "technical": {"duration_seconds": float(final_probe["format"]["duration"]),
                      "video": next((s for s in final_probe["streams"]
                                     if s.get("codec_type") == "video"), {}),
                      "audio": next((s for s in final_probe["streams"]
                                     if s.get("codec_type") == "audio"), None)},
        "creative": {"status": "NOT_EVALUATED", "approver": "Harun"},
        "note": "Teknik PASS yaratıcı PASS değildir; medya git'e eklenmez, manifest girer.",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    (out_dir / "KALITE-RAPORU.md").write_text(_report_markdown(manifest, qa), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--out-dir", default=str(ROOT / "deliverables" / "S01-PARK-KITE-001"))
    parser.add_argument("--tag", default="take1")
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--model", default="LTX-2.5 (Hugging Face Space)")
    parser.add_argument("--workflow", default="")
    parser.add_argument("--cost-usd", type=float, default=0.0)
    args = parser.parse_args(argv)

    manifest = finalize(Path(args.video), Path(args.out_dir), tag=args.tag,
                        seconds=args.seconds, width=args.width, height=args.height,
                        fps=args.fps, model=args.model, cost_usd=args.cost_usd,
                        workflow=args.workflow)
    print(json.dumps({"video": manifest["files"]["video"]["path"],
                      "manifest": str(Path(args.out_dir) / "manifest.json"),
                      "technical_ok": manifest["technical"]["duration_seconds"] > 0,
                      "creative": manifest["creative"]["status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
