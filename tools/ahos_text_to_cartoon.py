"""AHOS Studio-16: story text -> canonical plan -> honest 2D technical preview.

No spending, no cloud APIs, no claim of professional 3D or true lip-sync.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "tools" / "render_scene01_2d.py"
CAST = (
    "aden", "kaan", "esra", "ahmet", "esma", "harun", "veysel", "oznur",
    "salih", "medine", "davut", "fatos", "emos", "berzan", "aras", "ramin",
)
ALIASES = {"öz nur": "oznur", "öznur": "oznur", "fatoş": "fatos", "emoş": "emos",
           "salih": "salih", "ramîn": "ramin"}
NAMES = dict(zip(CAST, ("Aden","Kaan","Esra","Ahmet","Esma","Harun","Veysel",
                        "Öznur","Salih","Medine","Davut","Fatoş","Emoş","Berzan","Aras","Ramin")))
ACTIONS = {
    "yuru": ("yürü", "yur", "walk", "gez", "koş", "kos"),
    "wave": ("el sall", "salla", "selam", "wave"),
    "crawl": ("emekle", "emekli", "emek", "crawl"),
    "look": ("bak", "gör", "gor", "look"),
    "talk": ("konuş", "konus", "söyle", "soyle", "de ", "said", "talk"),
    "kite": ("uçurtma", "ucurtma", "kite"),
}


def parse_story(text: str, duration: int = 6) -> dict:
    text = " ".join(text.split()).strip()
    if not text or len(text) > 2000:
        raise ValueError("Hikaye 1-2000 karakter arasında olmalı.")
    if duration not in range(3, 21):
        raise ValueError("Teknik onizleme 3-20 saniye olabilir.")
    lower = text.casefold()
    char_names = [(k, v) for k, v in NAMES.items()]
    names = []
    for k, v in char_names:
        tests = (v.casefold(), k) + tuple(a for a, target in ALIASES.items() if target == k)
        if any(re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", lower) for name in tests):
            names.append(k)
    quoted = re.findall(r'[“"«](.+?)[”"»]', text)
    speech = quoted[0][:120] if quoted else ""
    has = {key: any(word in lower for word in words) for key, words in ACTIONS.items()}
    setting = ("ev" if any(x in lower for x in ("evde", "salon", "mutfak", "odada", "evin"))
               else "park" if any(x in lower for x in ("park", "bahçe", "bahce", "uçurtma", "ucurtma"))
               else "stüdyo")
    blockers = []
    if not names:
        blockers.append("Karakter adı tanınmadı. Kanondaki 16 isimden en az biri gerekli.")
    unsupported = [k for k in names if k not in ("aden", "kaan")]
    if unsupported:
        blockers.append("Animasyon rig'i olmayan karakterler: " + ", ".join(NAMES[x] for x in unsupported))
    if setting == "stüdyo":
        blockers.append("İstenen mekân bulunamadı; teknik önizleme için nötr stüdyo kullanılır.")
    if has["talk"] or speech:
        blockers.append("Doğrulanmış Türkçe karakter sesi ve fonem bazlı lip-sync yok; önizleme sessiz.")
    if any(x in lower for x in ("3d ", "üç boyut", "uc boyut")):
        blockers.append("3D mesh ve profesyonel yüz rig'i mevcut değil.")
    available = bool(names and not unsupported)
    shots = [
        {"start": 0, "end": round(duration / 3, 2), "action": "tanıtım"},
        {"start": round(duration / 3, 2), "end": round(2 * duration / 3, 2),
         "action": "hareket" if has["yuru"] or has["crawl"] else "tepki"},
        {"start": round(2 * duration / 3, 2), "end": duration,
         "action": "konuşma önizlemesi" if has["talk"] or speech else "kapanış"},
    ]
    return {
        "schema": "ahos.text-to-cartoon.plan.v1",
        "input": text,
        "cast": names,
        "cast_labels": [NAMES[x] for x in names],
        "setting": setting,
        "duration_s": duration,
        "actions": has,
        "quoted_dialogue": speech,
        "shots": shots,
        "technical_preview_supported": available,
        "blockers": blockers,
        "approved_character_assets_used": False,
        "note": "Görsel karakterler mevcut vektör testinden gelir, onaylı yüz rig'i değildir.",
    }


def _existing_renderer():
    spec = importlib.util.spec_from_file_location("ahos_vector_technical", ENGINE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _font(size: int):
    path = Path("C:/Windows/Fonts/arial.ttf")
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def _set(draw: ImageDraw.ImageDraw, plan: dict, t: float):
    # Internally composed environment: does NOT recreate a film-quality scene.
    W, H = 1920, 1080
    draw.rectangle((0, 0, W, 790), fill="#ADDBF2" if plan["setting"] != "ev" else "#E8D6B6")
    draw.rectangle((0, 790, W, H), fill="#85B768" if plan["setting"] != "ev" else "#D5B28B")
    if plan["setting"] == "park":
        for x in (160, 410, 1510, 1760):
            draw.rectangle((x-14, 565, x+14, 808), fill="#75563F")
            draw.ellipse((x-120, 425, x+120, 680), fill="#5CA264")
    if plan["setting"] == "ev":
        draw.rectangle((104, 310, 610, 820), fill="#EAD6BB", outline="#A88563", width=14)
        draw.rectangle((710, 400, 1050, 780), fill="#ACD7EC", outline="#8F735A", width=14)
        draw.rectangle((1240, 690, 1710, 820), fill="#AA7759")
    if plan["actions"]["kite"]:
        x, y = 1460 + math.sin(t * 1.5) * 20, 245 + math.sin(t) * 14
        draw.polygon(((x,y-78),(x+87,y),(x,y+78),(x-87,y)), fill="#EDC34C")
        draw.line(((x,y+78),(x+15,y+250)), fill="#9F7C63",width=5)


def _frame(plan: dict, t: float, module) -> Image.Image:
    W,H = 1920,1080
    im = Image.new("RGB",(W,H))
    d = ImageDraw.Draw(im)
    _set(d, plan, t)
    cast = plan["cast"]
    phase = t / plan["duration_s"]
    active = plan["actions"]
    if "aden" in cast:
        iswalk = active["yuru"] and phase < .48
        x = 320 + (310 * min(1, phase/.48)) if iswalk else (630 if active["yuru"] else 470)
        wave = (active["wave"] or active["kite"]) and .45 <= phase <= .82
        talking = (active["talk"] or plan["quoted_dialogue"]) and .65 <= phase <= .92
        st = {"walk":int(iswalk), "wave":int(wave), "look":int(phase>.3),
              "blink":int(t % 2.6 < .12), "talk":int(bool(talking)),
              "talk_shape":int(t*8)%4,"head_dx":18 if phase>.3 else 0}
        module.aden(d,x,920,t,st)
    if "kaan" in cast:
        move = active["crawl"] or ("aden" in cast and not active["wave"])
        x = 1150 - 120*min(1,phase/.6) if move else 1070
        module.kaan(d,x,930,t,{"crawl":int(bool(move)), "blink":int((t+.5)%2.7 < .13)})
    d.rectangle((0,0,W,120),fill="#283446")
    d.text((42,26),"AHOS STUDIO-16 | TEKNIK ONIZLEME",fill="white",font=_font(38))
    title = plan["input"][:115]
    d.rectangle((40,952,1880,1050),fill="#283446")
    d.text((72,968),title[:87],fill="#FFFFFF",font=_font(28))
    return im.resize((960,540),Image.Resampling.LANCZOS)


def render_preview(plan: dict, output: Path, fps: int = 12) -> dict:
    if not plan["technical_preview_supported"]:
        raise ValueError("Kanon karakterleri için mevcut rig yok; teknik video yapılmadı.")
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("FFmpeg/ffprobe bulunamadı.")
    output.parent.mkdir(parents=True, exist_ok=True)
    module = _existing_renderer()
    cmd = [ffmpeg, "-loglevel","error","-y",
           "-f","rawvideo","-pix_fmt","rgb24","-s","960x540",
           "-r",str(fps),"-i","pipe:0","-c:v","libx264","-preset","ultrafast",
           "-crf","25","-pix_fmt","yuv420p","-movflags","+faststart",
           "-an",str(output)]
    proc = subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE)
    frames = int(plan["duration_s"]*fps)
    first = None
    middle = None
    try:
        for i in range(frames):
            image = _frame(plan,i/fps,module)
            if i == 0:
                first = image.copy()
                image.save(output.parent / "first-frame.png")
            if i == frames // 2:
                middle = image.copy()
            proc.stdin.write(image.tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode("utf-8",errors="replace")
        code = proc.wait()
        if code: raise RuntimeError("FFmpeg exit %s: %s"%(code,err[-900:]))
    except Exception as exc:
        proc.kill()
        proc.wait()
        detail = proc.stderr.read().decode('utf-8', errors='replace')[-1800:]
        raise RuntimeError(f'Video encode error: {exc}; ffmpeg stderr: {detail}') from exc
    meta = json.loads(subprocess.check_output([ffprobe,"-v","error","-show_entries",
                   "format=duration:stream=codec_name,width,height,r_frame_rate",
                   "-of","json",str(output)],text=True))
    motion_verified = bool(first is not None and middle is not None and
                           ImageChops.difference(first, middle).getbbox() is not None)
    return {"status":"TECHNICAL_PREVIEW_NOT_PROFESSIONAL",
            "video":str(output),"sha256":hashlib.sha256(output.read_bytes()).hexdigest(),
            "frames":frames,"fps":fps,"duration_s":plan["duration_s"],
            "motion_verified":motion_verified,
            "probe":meta,"audio":"NONE","is_3d":False,
            "approved_character_identity":False,"production_ready":False,
            "blockers":plan["blockers"]+[
                "Yüksek kaliteli 3D mesh/rig, karakter sesleri ve sesli lip-sync henüz yok."
            ]}


def run_pipeline(prompt: str, out: Path, duration: int=6, plan_only: bool=False) -> dict:
    out.mkdir(parents=True,exist_ok=True)
    plan = parse_story(prompt,duration)
    (out/"story-plan.json").write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding="utf-8")
    if plan_only or not plan["technical_preview_supported"]:
        result = {"state":"PLANNED" if plan_only else "BLOCKED",
                  "plan":"story-plan.json","preview":None,"production_ready":False,
                  "blockers":plan["blockers"]}
    else:
        rendered = render_preview(plan,out/"technical-preview.mp4")
        (out/"technical-qa.json").write_text(json.dumps(rendered,ensure_ascii=False,indent=2),encoding="utf-8")
        result = {"state":"TECHNICAL_PREVIEW_READY","plan":"story-plan.json",
                  "preview":"technical-preview.mp4","production_ready":False,
                  "blockers":rendered["blockers"],"sha256":rendered["sha256"]}
    (out/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--prompt",required=True)
    parser.add_argument("--duration",type=int,default=6)
    parser.add_argument("--out",type=Path,default=ROOT/"deliverables"/"AHOS-TEXT-TO-CARTOON-DEMO")
    parser.add_argument("--plan-only",action="store_true")
    args=parser.parse_args(argv)
    result=run_pipeline(args.prompt,args.out,args.duration,args.plan_only)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result["state"]!="BLOCKED" else 2


if __name__=="__main__":
    raise SystemExit(main())
