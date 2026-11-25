"""Teknik QA raporu (G1): dosya, süre, çözünürlük, kare bütünlüğü, ses, altyazı. YARATICI kaliteyi ÖLÇMEZ.
Kullanım: python tools/tech_qa.py <klip.mp4> <render_stats.json|-> <çıktı.md>"""
import json, subprocess, sys, re, shutil, os, time
ff = shutil.which("ffmpeg") or "ffmpeg"; fp = shutil.which("ffprobe") or "ffprobe"

def run(a): return subprocess.run(a, capture_output=True, text=True)

def main(clip, stats_path, out):
    pr = json.loads(run([fp, "-v", "error", "-show_streams", "-show_format", "-of", "json", clip]).stdout)
    v = next((s for s in pr["streams"] if s["codec_type"] == "video"), {}); a = next((s for s in pr["streams"] if s["codec_type"] == "audio"), {})
    subs = [s for s in pr["streams"] if s["codec_type"] == "subtitle"]
    dur = float(pr["format"]["duration"])
    fr = run([ff, "-hide_banner", "-i", clip, "-vf", "freezedetect=n=-60dB:d=1.5,blackdetect=d=0.5:pix_th=0.05", "-an", "-f", "null", "-"]).stderr
    freezes = re.findall(r"freeze_start: ([\d.]+)", fr); blacks = re.findall(r"black_start:([\d.]+)", fr)
    au = run([ff, "-hide_banner", "-i", clip, "-af", "silencedetect=n=-50dB:d=1.5,volumedetect,astats=metadata=0:reset=0", "-vn", "-f", "null", "-"]).stderr
    sil = re.findall(r"silence_start: ([\d.]+)", au); mean = re.search(r"mean_volume: ([-\d.]+)", au); mx = re.search(r"max_volume: ([-\d.]+)", au)
    clip_ = re.findall(r"Number of samples.*?: (\d+)", au)
    st = json.load(open(stats_path)) if stats_path != "-" and os.path.exists(stats_path) else {}
    L = ["# Teknik QA — " + os.path.basename(clip), f"Üretim: {time.strftime('%Y-%m-%d %H:%M')}  | Bu rapor YARATICI kaliteyi ölçmez.", "",
         f"- Çözünürlük: {v.get('width')}x{v.get('height')}  | fps: {v.get('r_frame_rate')}  | codec: {v.get('codec_name')}/{a.get('codec_name')}",
         f"- Süre: {dur:.2f} s  | beklenen kare ≈ {round(dur * eval(v.get('r_frame_rate', '24/1')))}  | gerçek: {v.get('nb_frames')}",
         f"- Kare bütünlüğü (render_stats): {st.get('rendered')} üretildi / {st.get('missing')} eksik / yeniden deneme {st.get('retries')} / zaman aşımı {st.get('timeouts')} / eski kare taşındı {st.get('stale_moved')} / işçi {st.get('workers_start')}->{st.get('workers_end')} (boş bellek {st.get('mem_mb')} MB)",
         f"- Donuk kare aralıkları (≥1,5 sn): {freezes or 'yok'}", f"- Siyah kare: {blacks or 'yok'}",
         f"- Ses: ort {mean.group(1) if mean else '?'} dB, tepe {mx.group(1) if mx else '?'} dB, ≥1,5 sn sessizlik başlangıçları: {sil or 'yok'}",
         f"- Altyazı akışı: {len(subs)}", "",
         "Not: dB ortalaması ve donuk kare yokluğu 'iyi animasyon' veya 'iyi ses' sonucu DEĞİLDİR."]
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n"); print("\n".join(L))

if __name__ == "__main__": main(*sys.argv[1:4])
