#!/usr/bin/env python3
import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8188"
NODES = [
    "LoadImage",
    "CheckpointLoaderSimple",
    "LTXAVTextEncoderLoader",
    "CLIPTextEncode",
    "LTXVConditioning",
    "LTXVImgToVideoInplace",
    "LTXVImgToVideoConditionOnly",
    "LTXVEmptyLatentVideo",
    "RandomNoise",
    "KSamplerSelect",
    "BasicGuider",
    "SamplerCustomAdvanced",
    "VAEDecode",
    "CreateVideo",
    "SaveVideo",
]

for name in NODES:
    url = f"{BASE}/object_info/{name}"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            payload = json.load(response)
    except Exception as exc:
        print(f"SCHEMA {name}: ERROR {exc}")
        continue
    info = payload.get(name)
    if not info:
        print(f"SCHEMA {name}: MISSING")
        continue
    inputs = info.get("input", {})
    print(f"SCHEMA {name}: {json.dumps(inputs, sort_keys=True)}")
