$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$envRuntime = Join-Path $root ".env.runtime"
$privateRoot = Join-Path $root "runtime\private\animation-studio\audio"
$outPath = Join-Path $privateRoot "kokoro-worker-diagnostics.local.json"
$tmp = Join-Path $env:TEMP "studio006_kokoro_diag.py"

$endpointId = "4vygp64ky68w3z"
$endpointName = "miniverse-kokoro-tts-prod"

Write-Host "=== STUDIO-006 KOKORO WORKER DIAGNOSTICS ==="
Write-Host "No inference request will be sent."
Write-Host "No TTS will be generated."
Write-Host "This reads worker state + recent worker logs only."
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
if (-not $apiKey) {
    throw "RUNPOD_API_KEY not found."
}

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "AHOS Python venv not found."
}

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
out_path = Path(sys.argv[2])
api_key = os.environ["RUNPOD_API_KEY"]

BASE = "https://v2-rest.runpod.io/v2/serverless"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Accept": "application/json",
    "User-Agent": "AHOS-STUDIO-006",
}

SECRET_PATTERNS = [
    re.compile(r"rpa_[A-Za-z0-9_-]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"sk-[A-Za-z0-9_-]+"),
]

def redact(text: str) -> str:
    for p in SECRET_PATTERNS:
        text = p.sub("[REDACTED]", text)
    return text

def get_json(url: str):
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return e.code, {"error": redact(body)}
    except Exception as e:
        return None, {"error": redact(str(e))}

def read_sse(url: str, max_seconds: float = 8.0, max_items: int = 160):
    req_headers = dict(headers)
    req_headers["Accept"] = "text/event-stream"
    req = urllib.request.Request(url, headers=req_headers, method="GET")
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
                        line_text = redact(str(obj.get("line", "")))
                        items.append({
                            "source": str(obj.get("source", "")),
                            "line": line_text,
                            "ts": str(obj.get("ts", "")),
                        })
                    except Exception:
                        items.append({"source": "raw", "line": redact(payload), "ts": ""})
        return 200, items
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return e.code, [{"source": "error", "line": redact(body), "ts": ""}]
    except Exception as e:
        return None, [{"source": "error", "line": redact(str(e)), "ts": ""}]

workers_url = f"{BASE}/{endpoint_id}/workers"
status, payload = get_json(workers_url)

result = {
    "endpoint_id": endpoint_id,
    "workers_http_status": status,
    "summary": None,
    "workers": [],
    "logs": {},
}

if status != 200:
    result["worker_list_error"] = payload
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("WORKER LIST HTTP STATUS:", status)
    print("WORKER LIST ERROR:", payload.get("error"))
    sys.exit(2)

if isinstance(payload, dict):
    result["summary"] = payload.get("summary")
    workers = payload.get("workers") or payload.get("items") or payload.get("data") or []
elif isinstance(payload, list):
    workers = payload
else:
    workers = []

if isinstance(workers, dict):
    workers = workers.get("items") or workers.get("workers") or []

safe_workers = []
for w in workers:
    if not isinstance(w, dict):
        continue
    safe = {
        "id": str(w.get("id", "")),
        "status": str(w.get("status", "")),
        "gpuTypeId": str(w.get("gpuTypeId", "")),
        "gpuCount": w.get("gpuCount"),
        "dataCenterId": str(w.get("dataCenterId", "")),
        "image": str(w.get("image", "")),
        "startedAt": str(w.get("startedAt", "")),
        "isStale": w.get("isStale"),
        "version": w.get("version"),
    }
    safe_workers.append(safe)

result["workers"] = safe_workers

print("WORKER LIST: PASS")
print("SUMMARY:", json.dumps(result["summary"], ensure_ascii=False))
print("WORKER COUNT:", len(safe_workers))
for w in safe_workers:
    print(
        " -",
        w["id"],
        "STATUS=", w["status"],
        "GPU=", w["gpuTypeId"],
        "DC=", w["dataCenterId"],
    )

interesting = re.compile(
    r"(error|fail|fatal|traceback|health|listen|port|uvicorn|kokoro|model|cuda|ready|start|download|oom|memory)",
    re.I,
)

for w in safe_workers[:3]:
    wid = w["id"]
    if not wid:
        continue
    result["logs"][wid] = {}
    for source in ("system", "container"):
        url = (
            f"{BASE}/{endpoint_id}/workers/{urllib.parse.quote(wid, safe='')}/logs"
            f"?source={source}&tail=160"
        )
        log_status, items = read_sse(url)
        result["logs"][wid][source] = {
            "http_status": log_status,
            "items": items,
        }
        print()
        print(f"{source.upper()} LOGS worker={wid} HTTP={log_status}")
        selected = [x for x in items if interesting.search(x.get("line", ""))]
        if not selected:
            selected = items[-12:]
        for item in selected[-30:]:
            line = item.get("line", "")
            if line:
                print(" ", line[:500])

out_path.write_text(
    json.dumps(result, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print()
print("PRIVATE DIAGNOSTIC SAVED:", out_path)
'@

[IO.File]::WriteAllText($tmp, $pyCode, [Text.UTF8Encoding]::new($false))

$previousKey = $env:RUNPOD_API_KEY
$env:RUNPOD_API_KEY = $apiKey
try {
    & $python $tmp $endpointId $outPath
    $exitCode = $LASTEXITCODE
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
if ($exitCode -eq 0) {
    Write-Host "=== KOKORO DIAGNOSTICS COMPLETE ==="
    Write-Host "Worker state/log read: PASS"
    Write-Host "Inference requests: 0"
    Write-Host "TTS requests: 0"
    Write-Host "This diagnostic does not start a new inference job."
} else {
    Write-Host "=== KOKORO DIAGNOSTICS COULD NOT READ WORKERS ==="
    Write-Host "Exit code:" $exitCode
    Write-Host "No inference/TTS request was sent."
}
