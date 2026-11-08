$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$envRuntime = Join-Path $root ".env.runtime"
$privateRoot = Join-Path $root "runtime\private\animation-studio\audio"
$outPath = Join-Path $privateRoot "kokoro-post-disk-verify.local.json"
$tmp = Join-Path $env:TEMP "studio006_kokoro_postdisk.py"

$endpointId = "4vygp64ky68w3z"
$endpointName = "miniverse-kokoro-tts-prod"

Write-Host "=== STUDIO-006 KOKORO POST-DISK VERIFY V2 ==="
Write-Host "Purpose: verify 40 GB through GraphQL and inspect the CURRENT worker's newest logs."
Write-Host "Inference/TTS requests: 0"
Write-Host "GPU jobs submitted: 0"
Write-Host ""

function Get-EnvValue([string]$path, [string]$name) {
    if (-not (Test-Path $path)) { return $null }
    $line = Get-Content $path -ErrorAction Stop |
        Where-Object { $_ -match "^\s*$([regex]::Escape($name))\s*=" } |
        Select-Object -First 1
    if (-not $line) { return $null }
    $value = ($line -split "=", 2)[1].Trim()
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
        ($value.StartsWith("'") -and $value.EndsWith("'"))) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    return $value
}

$apiKey = $env:RUNPOD_API_KEY
if (-not $apiKey) {
    $apiKey = Get-EnvValue $envRuntime "RUNPOD_API_KEY"
}
if (-not $apiKey) { throw "RUNPOD_API_KEY not found." }

$templateId = Get-EnvValue $envRuntime "RUNPOD_KOKORO_TEMPLATE_ID"
if (-not $templateId) {
    $templateId = "5ji3u7nv2b"
}

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "AHOS Python venv not found." }

New-Item -ItemType Directory -Force -Path $privateRoot | Out-Null

$pyCode = @'
from __future__ import annotations

import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

endpoint_id = sys.argv[1]
template_id = sys.argv[2]
out_path = Path(sys.argv[3])
api_key = os.environ["RUNPOD_API_KEY"]

AUTH = {"Authorization": f"Bearer {api_key}", "User-Agent": "AHOS-STUDIO-006"}
JSON_HEADERS = dict(AUTH, **{"Accept": "application/json"})
GQL_HEADERS = dict(JSON_HEADERS, **{"Content-Type": "application/json"})

def request_json(url: str, method="GET", data=None, headers=None, timeout=30):
    hdrs = headers or JSON_HEADERS
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
        return r.status, json.loads(raw)

def read_sse(url: str, max_seconds=8.0, max_items=240):
    headers = dict(AUTH)
    headers["Accept"] = "text/event-stream"
    req = urllib.request.Request(url, headers=headers, method="GET")
    items = []
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            while len(items) < max_items and (time.time() - started) < max_seconds:
                try:
                    line = r.readline()
                except socket.timeout:
                    break
                if not line:
                    break
                text = line.decode("utf-8", "replace").strip()
                if text.startswith("data:"):
                    payload = text[5:].strip()
                    try:
                        obj = json.loads(payload)
                        items.append({
                            "source": str(obj.get("source", "")),
                            "line": str(obj.get("line", "")),
                            "ts": str(obj.get("ts", "")),
                        })
                    except Exception:
                        pass
        return 200, items
    except urllib.error.HTTPError as e:
        return e.code, []
    except Exception:
        return None, []

# 1) GraphQL template disk check
query = """
query GetTemplate($id: String!) {
  podTemplate(id: $id) {
    id
    name
    imageName
    containerDiskInGb
  }
}
"""
_, gql = request_json(
    "https://api.runpod.io/graphql",
    method="POST",
    data={"query": query, "variables": {"id": template_id}},
    headers=GQL_HEADERS,
)
tmpl = ((gql.get("data") or {}).get("podTemplate") or {})
disk_gb = tmpl.get("containerDiskInGb")

print("TEMPLATE:", tmpl.get("name"))
print("IMAGE:", tmpl.get("imageName"))
print("CONTAINER DISK GB:", disk_gb)

# 2) Current worker list
_, workers_payload = request_json(
    f"https://v2-rest.runpod.io/v2/serverless/{endpoint_id}/workers"
)
summary = workers_payload.get("summary") if isinstance(workers_payload, dict) else None
workers = []
if isinstance(workers_payload, dict):
    workers = workers_payload.get("workers") or workers_payload.get("items") or workers_payload.get("data") or []
if isinstance(workers, dict):
    workers = workers.get("items") or workers.get("workers") or []

print("SUMMARY:", json.dumps(summary, ensure_ascii=False))
print("WORKER COUNT:", len(workers))

safe_workers = []
logs = {}
for w in workers:
    if not isinstance(w, dict):
        continue
    wid = str(w.get("id", ""))
    safe = {
        "id": wid,
        "status": str(w.get("status", "")),
        "isStale": w.get("isStale"),
        "image": str(w.get("image", "")),
        "startedAt": str(w.get("startedAt", "")),
        "gpuTypeId": str(w.get("gpuTypeId", "")),
        "dataCenterId": str(w.get("dataCenterId", "")),
    }
    safe_workers.append(safe)
    print("WORKER:", safe)

    if not wid:
        continue

    logs[wid] = {}
    for source in ("system", "container"):
        url = (
            f"https://v2-rest.runpod.io/v2/serverless/{endpoint_id}/workers/"
            f"{urllib.parse.quote(wid, safe='')}/logs?source={source}&tail=240"
        )
        status, items = read_sse(url)
        logs[wid][source] = {"http_status": status, "items": items}

        print()
        print(f"{source.upper()} LOGS HTTP={status}")
        # Show the newest relevant lines, with timestamps.
        interesting = re.compile(
            r"(no space left|failed to pull image|failed to register layer|model ready|"
            r"uvicorn|application startup|health|listening|started server|error|fatal|"
            r"traceback|cuda|kokoro|download|ready)",
            re.I,
        )
        selected = [x for x in items if interesting.search(x.get("line", ""))]
        if not selected:
            selected = items[-20:]
        for item in selected[-40:]:
            print(f"  {item.get('ts','')} | {item.get('line','')[:700]}")

# 3) Conservative interpretation.
all_lines = []
for wid, group in logs.items():
    for source in ("system", "container"):
        all_lines.extend(group.get(source, {}).get("items", []))

def parse_ts(x):
    return x.get("ts", "")

no_space = [x for x in all_lines if "no space left on device" in x.get("line", "").lower()]
success = [
    x for x in all_lines
    if re.search(r"(model ready|application startup complete|uvicorn running|started server process)", x.get("line", ""), re.I)
]

latest_no_space = max(no_space, key=parse_ts, default=None)
latest_success = max(success, key=parse_ts, default=None)

disk_pass = (str(disk_gb) == "40" or disk_gb == 40)
post_fix_success = False
if latest_success:
    if latest_no_space:
        post_fix_success = parse_ts(latest_success) > parse_ts(latest_no_space)
    else:
        post_fix_success = True

print()
print("40 GB DISK VERIFIED:", "PASS" if disk_pass else f"NO ({disk_gb})")
print("LATEST NO-SPACE ERROR:", latest_no_space["ts"] if latest_no_space else "NONE")
print("LATEST STARTUP-SUCCESS SIGNAL:", latest_success["ts"] if latest_success else "NONE")
print("SUCCESS AFTER LAST NO-SPACE:", post_fix_success)

result = {
    "endpoint_id": endpoint_id,
    "template_id": template_id,
    "container_disk_gb": disk_gb,
    "disk_verified_40gb": disk_pass,
    "summary": summary,
    "workers": safe_workers,
    "latest_no_space": latest_no_space,
    "latest_success": latest_success,
    "success_after_last_no_space": post_fix_success,
    "logs": logs,
}
out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print("PRIVATE RESULT:", out_path)
'@

[IO.File]::WriteAllText($tmp, $pyCode, [Text.UTF8Encoding]::new($false))

$previousKey = $env:RUNPOD_API_KEY
$env:RUNPOD_API_KEY = $apiKey

try {
    & $python $tmp $endpointId $templateId $outPath
    if ($LASTEXITCODE -ne 0) {
        throw "Post-disk verification failed."
    }
}
finally {
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    if ($null -eq $previousKey) {
        Remove-Item Env:\RUNPOD_API_KEY -ErrorAction SilentlyContinue
    } else {
        $env:RUNPOD_API_KEY = $previousKey
    }
}

Write-Host ""
Write-Host "=== STUDIO-006 POST-DISK VERIFY COMPLETE ==="
Write-Host "No inference request sent."
Write-Host "No TTS request sent."
Write-Host "No new GPU job submitted."
Write-Host "NEXT: if 40 GB is PASS and logs show a newer startup success, retry one /health request."
