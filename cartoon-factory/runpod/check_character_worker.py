from __future__ import annotations

import json
import os
import sys

import requests

endpoint = os.getenv("CHARACTER_COMFY_ENDPOINT", "").strip()
api_key = os.getenv("RUNPOD_API_KEY", "").strip()
if not endpoint:
    raise SystemExit("CHARACTER_COMFY_ENDPOINT is missing")

payload = {
    "input": {
        "positive_prompt": "friendly original 2D children's cartoon character, full body, clean line art, plain background",
        "negative_prompt": "photorealistic, watermark, text, malformed anatomy",
        "seed": 12345,
    }
}
headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
r = requests.post(endpoint, json=payload, headers=headers, timeout=900)
print("status:", r.status_code)
try:
    print(json.dumps(r.json(), indent=2)[:4000])
except Exception:
    print(r.text[:4000])
if not r.ok:
    sys.exit(1)
