"""AHOS objective video/audio quality signals, without GPU or false creative scoring.

Analyze a REAL file using ffprobe and ffmpeg. This catches severe freezes,
black footage, silent dialogue, wrong resolution/FPS and missing media streams.

Objective signal PASS does NOT certify character identity, lip sync, acting,
story adherence, license, or professional film quality.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path


class TechnicalMediaError(RuntimeError):
    pass


def _probe(video: Path):
    exe=shutil.which("ffprobe")
    if exe is None:
        raise TechnicalMediaError("ffprobe not installed")
    try:
        result=subprocess.run(
            [exe,"-v","error","-show_entries",
             "format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate",
             "-of","json",str(video)],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=35,check=True)
        obj=json.loads(result.stdout)
    except (subprocess.SubprocessError,ValueError) as exc:
        raise TechnicalMediaError("Cannot decode real media streams") from exc
    return obj


def _ranges(stderr,begin_key,end_key,duration_key,total):
    """Conservatively include open-ended intervals as extending to end."""
    found=[]
    starts=[]
    for line in stderr.splitlines():
        if begin_key in line:
            match=re.search(re.escape(begin_key)+r"\s*:?\s*([0-9]+(?:\.[0-9]+)?)",line)
            if match:
                starts.append(float(match.group(1)))
        if duration_key in line and end_key in line:
            start_match=re.search(re.escape(begin_key)+r"\s*:?\s*([0-9]+(?:\.[0-9]+)?)",line)
            end_match=re.search(re.escape(end_key)+r"\s*:?\s*([0-9]+(?:\.[0-9]+)?)",line)
            if end_match:
                end=float(end_match.group(1))
                if start_match:
                    start=float(start_match.group(1))
                    if starts and abs(starts[-1]-start)<.001:
                        starts.pop()
                elif starts:
                    start=starts.pop(0)
                else:
                    continue
                found.append((max(0,start),min(total,end)))
    found.extend((x,total) for x in starts if x<total)
    return [(start,end) for start,end in found if end>=start]


def _total(intervals):
    """Union lengths of potentially overlapping diagnostics."""
    if not intervals:
        return 0.
    intervals=sorted(intervals)
    merged=[]
    for a,b in intervals:
        if not merged or a>merged[-1][1]:
            merged.append([a,b])
        else:
            merged[-1][1]=max(merged[-1][1],b)
    return round(sum(b-a for a,b in merged),3)


def _rate(value):
    if not isinstance(value,str):
        raise TechnicalMediaError("Video frame rate unavailable")
    try:
        if "/" in value:
            num,den=map(int,value.split("/"))
            return num/den
        return float(value)
    except (ValueError,ZeroDivisionError) as exc:
        raise TechnicalMediaError("Invalid video frame rate") from exc


def assess(path: Path, *, dialogue=False, min_width=1280,
           min_height=720, min_seconds=1, max_seconds=120):
    """Analyze a bounded shot. For longer edits, segment first and assess all segments."""
    source=Path(path)
    if not source.is_file() or source.stat().st_size<100000:
        raise TechnicalMediaError("Real nontrivial media file missing")
    if source.stat().st_size>2*1024**3:
        raise TechnicalMediaError("File too large for bounded individual shot analysis")
    metadata=_probe(source)
    streams=metadata.get("streams",[])
    video=[s for s in streams if s.get("codec_type")=="video"]
    audio=[s for s in streams if s.get("codec_type")=="audio"]
    if not video or not audio:
        raise TechnicalMediaError("Real audio AND video streams required")
    try:
        duration=float(metadata.get("format",{}).get("duration","nan"))
    except ValueError as exc:
        raise TechnicalMediaError("Invalid duration") from exc
    if not math.isfinite(duration) or not min_seconds<=duration<=max_seconds:
        raise TechnicalMediaError("Invalid or unbounded shot duration; segment long films")
    v=video[0]
    width,height=v.get("width",0),v.get("height",0)
    fps=_rate(v.get("avg_frame_rate","0/0"))
    if width<min_width or height<min_height:
        raise TechnicalMediaError("Below minimum shot resolution")
    if not 23.95<=fps<=24.05:
        raise TechnicalMediaError("Wrong frame rate, requires approximately 24fps")
    exe=shutil.which("ffmpeg")
    if not exe:
        raise TechnicalMediaError("ffmpeg not installed")
    # Run visual and audio diagnostics on the original decoded media.
    cmd=[exe,"-hide_banner","-nostats","-v","info","-i",str(source),
         "-map","0:v:0","-map","0:a:0",
         "-vf","blackdetect=d=0.35:pix_th=0.10,freezedetect=n=-50dB:d=0.65",
         "-af","silencedetect=noise=-42dB:d=0.75",
         "-f","null","-"]
    try:
        run=subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                           text=True,timeout=min(300,max(40,int(duration*4)+25)))
    except subprocess.TimeoutExpired as exc:
        raise TechnicalMediaError("Media diagnostic timed out; never certify partial review") from exc
    if run.returncode:
        raise TechnicalMediaError("FFmpeg failed while decoding the complete shot")
    logs=run.stderr
    black=_ranges(logs,"black_start","black_end","black_duration",duration)
    frozen=_ranges(logs,"freeze_start","freeze_end","freeze_duration",duration)
    silent=_ranges(logs,"silence_start","silence_end","silence_duration",duration)
    # ffmpeg blackdetect lines sometimes end at black_end only; the parser
    # requires both start and end to avoid attributing unrelated diagnostics.
    black_s=_total(black)
    freeze_s=_total(frozen)
    silence_s=_total(silent)
    failures=[]
    if black_s>min(0.8,duration*.25):
        failures.append("EXCESSIVE_BLACK_FRAMES")
    if freeze_s>min(1.25,duration*.35):
        failures.append("EXCESSIVE_FROZEN_FRAMES")
    if dialogue and silence_s>min(1.25,duration*.35):
        failures.append("EXCESSIVE_DIALOGUE_SILENCE")
    h=hashlib.sha256()
    with source.open("rb") as stream:
        for piece in iter(lambda:stream.read(1024*1024),b""):
            h.update(piece)
    return {
        "schema":"ahos.media.objective-qa.v1",
        "artifact_sha256":h.hexdigest(),
        "duration_seconds":round(duration,3),
        "width":width,"height":height,"fps":round(fps,3),
        "has_video":True,"has_audio":True,
        "objective_technical_status":"PASSED" if not failures else "FAILED",
        "black_seconds":black_s,"frozen_seconds":freeze_s,
        "silence_seconds":silence_s,
        "dialogue_expected":bool(dialogue),
        "failures":failures,
        "creative_quality_verified":False,
        "actor_identity_verified":False,
        "lip_sync_verified":False,
        "commercial_rights_verified":False,
        "production_ready":False,
    }


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--video",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    parser.add_argument("--dialogue",action="store_true")
    parser.add_argument("--min-width",type=int,default=1280)
    parser.add_argument("--min-height",type=int,default=720)
    args=parser.parse_args(argv)
    try:
        result=assess(args.video,dialogue=args.dialogue,
                      min_width=args.min_width,min_height=args.min_height)
    except TechnicalMediaError as exc:
        result={"schema":"ahos.media.objective-qa.v1",
                "objective_technical_status":"BLOCKED",
                "reason":str(exc),"creative_quality_verified":False,
                "production_ready":False}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result["objective_technical_status"]=="PASSED" else 2


if __name__=="__main__":
    raise SystemExit(main())
