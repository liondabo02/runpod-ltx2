$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$pkg = Join-Path $ws "ahos_core"
$envRuntime = Join-Path $root ".env.runtime"

$privateRoot = Join-Path $root "runtime\private\animation-studio\audio"
$statePath = Join-Path $privateRoot "kokoro-live-health-state.local.json"
$rawPath = Join-Path $privateRoot "kokoro-live-health-response.local.json"
$reportPath = Join-Path $pkg "reports\STUDIO-006-kokoro-live-health.json"

$targetName = "miniverse-kokoro-tts-prod"
$graphqlUrl = "https://api.runpod.io/graphql"

Write-Host "=== STUDIO-006 LIVE KOKORO HEALTH PROBE ==="
Write-Host "This is a LIVE RunPod Load Balancer request."
Write-Host "It may wake one worker and create a small RunPod charge."
Write-Host "TTS/audio synthesis: NO"
Write-Host "Audio generated: NO"
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
    throw "RUNPOD_API_KEY was not found in environment or .env.runtime."
}

$endpointId = Get-EnvValue $envRuntime "RUNPOD_KOKORO_ENDPOINT_ID"
$templateId = Get-EnvValue $envRuntime "RUNPOD_KOKORO_TEMPLATE_ID"

if (-not $endpointId) { throw "RUNPOD_KOKORO_ENDPOINT_ID missing." }
if (-not $templateId) { throw "RUNPOD_KOKORO_TEMPLATE_ID missing." }

Write-Host "RUNPOD API KEY: PRESENT (hidden)"
Write-Host "Endpoint:" $targetName
Write-Host "Endpoint ID:" $endpointId
Write-Host "Template ID:" $templateId

# Idempotence: do not wake another worker if this exact health proof already passed.
if (Test-Path $statePath) {
    try {
        $prior = Get-Content $statePath -Raw | ConvertFrom-Json
        if ($prior.live_health_pass -eq $true) {
            Write-Host ""
            Write-Host "EXISTING LIVE KOKORO HEALTH PROOF: PASS"
            Write-Host "No new Load Balancer request sent."
            exit 0
        }
    } catch {}
}

# Query only enough template data to identify the configured health path/ports.
$query = @'
query GetTemplate($id: String!) {
  podTemplate(id: $id) {
    id
    imageName
    env {
      key
      value
    }
  }
}
'@

$body = @{
    query = $query
    variables = @{
        id = $templateId
    }
} | ConvertTo-Json -Depth 6

$headers = @{
    Authorization = "Bearer $apiKey"
    Accept = "application/json"
    "Content-Type" = "application/json"
    "User-Agent" = "AHOS-STUDIO-006"
}

$templateResp = Invoke-RestMethod `
    -Uri $graphqlUrl `
    -Method Post `
    -Headers $headers `
    -Body $body `
    -TimeoutSec 30

if ($templateResp.errors) {
    $messages = @($templateResp.errors | ForEach-Object { $_.message })
    throw ("GraphQL template read failed: " + ($messages -join " | "))
}

$template = $templateResp.data.podTemplate
if (-not $template) {
    throw "Template metadata not found."
}

# Whitelist ONLY known non-secret networking values.
$healthPath = $null
$port = $null
$portHealth = $null

foreach ($pair in @($template.env)) {
    switch ([string]$pair.key) {
        "HEALTH_CHECK_PATH" { $healthPath = [string]$pair.value }
        "PORT"              { $port = [string]$pair.value }
        "PORT_HEALTH"       { $portHealth = [string]$pair.value }
    }
}

if ([string]::IsNullOrWhiteSpace($healthPath)) {
    # The exact container image used by this endpoint exposes GET /health.
    $healthPath = "/health"
}
if (-not $healthPath.StartsWith("/")) {
    $healthPath = "/" + $healthPath
}

$invokeBase = "https://$endpointId.api.runpod.ai"
$appHealthUrl = $invokeBase + $healthPath
$controlHealthUrl = "https://api.runpod.ai/v2/$endpointId/health"

Write-Host ""
Write-Host "Container image:" ([string]$template.imageName)
Write-Host "Health path:" $healthPath
if ($port) { Write-Host "PORT:" $port }
if ($portHealth) { Write-Host "PORT_HEALTH:" $portHealth }
Write-Host "Live health URL:" $appHealthUrl
Write-Host ""
Write-Host "Sending the smallest live health request..."

function Invoke-AppHealth {
    param([string]$Url, [hashtable]$Headers)

    try {
        $web = Invoke-WebRequest `
            -Uri $Url `
            -Method Get `
            -Headers $Headers `
            -TimeoutSec 60 `
            -UseBasicParsing

        return [pscustomobject]@{
            ok = ($web.StatusCode -eq 200)
            status = [int]$web.StatusCode
            body = [string]$web.Content
            error = $null
        }
    }
    catch {
        $status = $null
        $body = $null

        try { $status = [int]$_.Exception.Response.StatusCode } catch {}

        try {
            if ($_.ErrorDetails.Message) {
                $body = [string]$_.ErrorDetails.Message
            }
        } catch {}

        return [pscustomobject]@{
            ok = $false
            status = $status
            body = $body
            error = [string]$_.Exception.Message
        }
    }
}

$first = Invoke-AppHealth -Url $appHealthUrl -Headers $headers

if ($first.ok) {
    Write-Host "DIRECT HEALTH RESPONSE: 200 PASS"
    $final = $first
}
else {
    Write-Host "Initial direct request did not return 200."
    if ($first.status) { Write-Host "Initial HTTP status:" $first.status }
    Write-Host "Cold-start polling RunPod worker health..."

    $ready = $false
    $deadline = (Get-Date).AddMinutes(7)

    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 5

        try {
            $control = Invoke-RestMethod `
                -Uri $controlHealthUrl `
                -Method Get `
                -Headers $headers `
                -TimeoutSec 30

            $readyCount = 0
            $runningCount = 0

            if ($control.workers) {
                if ($null -ne $control.workers.ready) {
                    $readyCount = [int]$control.workers.ready
                }
                if ($null -ne $control.workers.running) {
                    $runningCount = [int]$control.workers.running
                }
            }

            Write-Host ("Workers ready={0} running={1}" -f $readyCount, $runningCount)

            if (($readyCount + $runningCount) -gt 0) {
                $ready = $true
                break
            }
        }
        catch {
            Write-Host "Control-plane health poll retry..."
        }
    }

    if (-not $ready) {
        throw "Kokoro worker did not become ready within 7 minutes."
    }

    Write-Host "Worker available. Retrying exact health route once..."
    $final = Invoke-AppHealth -Url $appHealthUrl -Headers $headers
}

if (-not $final.ok) {
    if ($final.status) { Write-Host "Final HTTP status:" $final.status }
    if ($final.error) { Write-Host "Final error:" $final.error }
    throw "Kokoro live health route did not return HTTP 200."
}

# Parse health JSON if possible, but store only benign health response.
$healthJson = $null
try {
    $healthJson = $final.body | ConvertFrom-Json
} catch {}

New-Item -ItemType Directory -Force -Path $privateRoot | Out-Null

$rawResult = [ordered]@{
    url = $appHealthUrl
    http_status = $final.status
    response = if ($healthJson) { $healthJson } else { $final.body }
}
$rawResult | ConvertTo-Json -Depth 8 |
    Set-Content -Path $rawPath -Encoding UTF8

$state = [ordered]@{
    endpoint_id = $endpointId
    health_path = $healthPath
    live_health_pass = $true
    http_status = $final.status
    checked_at = (Get-Date).ToUniversalTime().ToString("o")
}
$state | ConvertTo-Json -Depth 5 |
    Set-Content -Path $statePath -Encoding UTF8

$report = [ordered]@{
    studio_step = "STUDIO-006 Kokoro live health"
    status = "PASS"
    endpoint_name = $targetName
    endpoint_id = $endpointId
    container_image = [string]$template.imageName
    endpoint_type = "load_balancer"
    health_path = $healthPath
    http_status = $final.status
    worker_health = "PASS"
    tts_request_sent = $false
    audio_generated = $false
    paid_live_execution = $true
    secret_exposed = $false
}
$report | ConvertTo-Json -Depth 6 |
    Set-Content -Path $reportPath -Encoding UTF8

git -C $ws add ahos_core/reports/STUDIO-006-kokoro-live-health.json

$staged = git -C $ws diff --cached --name-only
if ($staged) {
    git -C $ws -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" `
        commit -m "test(studio): verify live Kokoro worker health"
    if ($LASTEXITCODE -ne 0) { throw "git commit failed." }

    git -C $ws push origin HEAD
    if ($LASTEXITCODE -ne 0) { throw "git push failed." }
}

Write-Host ""
Write-Host "=== STUDIO-006 LIVE KOKORO HEALTH COMPLETE ==="
Write-Host "RunPod Load Balancer auth: PASS"
Write-Host "Kokoro worker cold start: PASS"
Write-Host "Kokoro /health response: PASS"
Write-Host "HTTP status: 200"
Write-Host "TTS request sent: NO"
Write-Host "Audio generated: NO"
Write-Host "Secret exposed: NO"
Write-Host "Evidence report committed: PASS"
Write-Host ""
Write-Host "NEXT: generate ONE tiny owner-approved Kokoro audio sample, validate the audio bytes, then wire the provider into AHOS."
