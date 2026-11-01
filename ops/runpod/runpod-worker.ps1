# AHOS ↔ RunPod worker (GPU/video kuyruğu)
# RunPod kapalıyken (AHOS_RUNPOD_ENABLED != 1) istekleri "unconfigured" olarak
# sonuçlandırır; sahte başarı üretmez.
#
# Kullanım: powershell -NoProfile -ExecutionPolicy Bypass -File ops\runpod\runpod-worker.ps1
param(
    [string]$Runtime = 'C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime',
    [string]$Endpoint = $env:AHOS_RUNPOD_ENDPOINT,
    [int]$PollSeconds = 5,
    [string]$PidFile = ''
)

$ErrorActionPreference = 'Stop'
if (-not $PidFile) { $PidFile = Join-Path $Runtime 'runpod-worker.pid' }
if (Test-Path $PidFile) {
    $existing = Get-Content $PidFile -ErrorAction SilentlyContinue
    if ($existing -and (Get-Process -Id $existing -ErrorAction SilentlyContinue)) { "zaten calisiyor: pid $existing"; exit 2 }
}
Set-Content -Path $PidFile -Value $PID -Encoding ascii

$QueueDir = Join-Path $Runtime 'runpod-queue'
$ResultDir = Join-Path $Runtime 'runpod-results'
New-Item -ItemType Directory -Force -Path $QueueDir, $ResultDir | Out-Null

while ($true) {
    foreach ($request in (Get-ChildItem $QueueDir -Filter '*.json' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime)) {
        $payload = Get-Content $request.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
        $job = [string]$payload.job_id
        $started = Get-Date
        $status = 'unconfigured'
        $detail = 'RunPod uç noktası tanımlı değil (AHOS_RUNPOD_ENDPOINT)'

        if ($Endpoint) {
            try {
                $body = @{
                    input = @{
                        prompt = [string]$payload.prompt
                        kind   = [string]$payload.kind
                    }
                } | ConvertTo-Json -Depth 5
                $response = Invoke-RestMethod -Uri $Endpoint -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 300
                $status = 'completed'
                $detail = ($response | ConvertTo-Json -Depth 5 -Compress)
            } catch {
                $status = 'failed'
                $detail = $_.Exception.Message
            }
        }

        $result = @{
            job_id = $job
            status = $status
            detail = $detail
            seconds = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)
            at = (Get-Date).ToString('o')
        } | ConvertTo-Json -Depth 5
        $safe = ($job -replace '[^A-Za-z0-9_-]', '_')
        Set-Content -Path (Join-Path $ResultDir ($safe + '.json')) -Value $result -Encoding utf8
        Remove-Item $request.FullName -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds $PollSeconds
}
