#!/usr/bin/env python3
"""Hazır bir bölümü (senaryo+ses var) yeniden render eder; yazarlar odasını tekrar çalıştırmaz.
python tools\\render_episode.py --series-id X --episode e001 --seconds 480 --render-seconds 12"""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import render_worker as rw  # noqa: E402
import video_qa as vqa  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series-id", required=True); ap.add_argument("--episode", required=True)
    ap.add_argument("--seconds", type=int, default=480); ap.add_argument("--render-seconds", type=int, default=12)
    a = ap.parse_args()
    sdir = os.path.join(ROOT, "series", a.series_id)
    out = os.path.join(sdir, "episodes", a.episode)
    bible = json.load(open(os.path.join(sdir, "series-bible.json"), encoding="utf-8"))
    t1 = float(a.seconds) if a.render_seconds < 0 else min(float(a.render_seconds), float(a.seconds))
    fr = os.path.join(out, "render", "frames")
    if os.path.isdir(fr):  # motor değiştiyse eski kareler yeniden kullanılmasın (silmek yerine kenara al)
        os.rename(fr, fr.replace("frames", "frames_old_%d" % int(__import__("time").time())))
    rm = rw.run(out, bible, 0.0, t1, sdir)
    print("RENDER:", json.dumps(rm, ensure_ascii=False)[:600])
    if rm.get("status") != "PASSED":
        sys.exit(2)
    vq = vqa.check(rm["clip"], t1)
    json.dump(vq, open(os.path.join(out, "video_quality_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("VIDEO_QA:", vq["verdict"], "; ".join(vq["problems"]))
    print("CLIP:", rm["clip"])


if __name__ == "__main__":
    main()
