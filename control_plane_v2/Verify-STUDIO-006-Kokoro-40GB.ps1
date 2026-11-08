$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$envRuntime = Join-Path $root ".env.runtime"

$endpointId = "4vygp64ky68w3z"
$endpointName = "miniverse-kokoro-tts-prod"
$v1Url = "https://rest.runpod.io/v1/endpoints/$endpointId?includeTemplate=true&includeWorkers=true"
$v2WorkersUrl = "https://v2-rest.runpod.io/v2/serverless/$endpointId/workers"

Write-Host "=== STUDIO-006 KOKORO POST-DISK-CHANGE VERIFY ==="
Write-Host "Purpose: verify the 40 GB disk change and confirm old workers are gone/stale."
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

$headers = @{
    Authorization = "Bearer $apiKey"
    Accept = "application/json"
    "User-Agent" = "AHOS-STUDIO-006"
}

Write-Host "RUNPOD API KEY: PRESENT (hidden)"
Write-Host "Endpoint:" $endpointName
Write-Host ""

$diskGb = $null
$templateId = $null

try {
    $ep = Invoke-RestMethod -Uri $v1Url -Method Get -Headers $headers -TimeoutSec 30
    $templateId = [string]$ep.templateId

    if ($ep.template -and $null -ne $ep.template.containerDiskInGb) {
        $diskGb = [int]$ep.template.containerDiskInGb
    } elseif ($null -ne $ep.containerDiskInGb) {
        $diskGb = [int]$ep.containerDiskInGb
    }

    Write-Host "Endpoint metadata: PASS"
    if ($templateId) { Write-Host "Template ID:" $templateId }
    if ($null -ne $diskGb) {
        Write-Host "Container disk GB:" $diskGb
    } else {
        Write-Host "Container disk GB: not returned by v1 endpoint read"
    }
}
catch {
    Write-Host "Endpoint metadata read failed:" $_.Exception.Message
}

if ($null -eq $diskGb -and $templateId) {
    try {
        $query = @'
query GetTemplate($id: String!) {
  podTemplate(id: $id) {
    id
    containerDiskInGb
  }
}
'@
        $body = @{
            query = $query
            variables = @{ id = $templateId }
        } | ConvertTo-Json -Depth 6

        $gqlHeaders = @{
            Authorization = "Bearer $apiKey"
            Accept = "application/json"
            "Content-Type" = "application/json"
            "User-Agent" = "AHOS-STUDIO-006"
        }

        $resp = Invoke-RestMethod `
            -Uri "https://api.runpod.io/graphql" `
            -Method Post `
            -Headers $gqlHeaders `
            -Body $body `
            -TimeoutSec 30

        if ($resp.data.podTemplate -and $null -ne $resp.data.podTemplate.containerDiskInGb) {
            $diskGb = [int]$resp.data.podTemplate.containerDiskInGb
            Write-Host "Container disk GB (GraphQL):" $diskGb
        }
    }
    catch {
        Write-Host "Template disk fallback read failed:" $_.Exception.Message
    }
}

Write-Host ""
Write-Host "Reading current worker list..."

try {
    $workers = Invoke-RestMethod `
        -Uri $v2WorkersUrl `
        -Method Get `
        -Headers $headers `
        -TimeoutSec 30

    Write-Host "Worker list: PASS"

    if ($workers.summary) {
        Write-Host "SUMMARY:"
        Write-Host "  total:" $workers.summary.total
        Write-Host "  idle:" $workers.summary.idle
        Write-Host "  initializing:" $workers.summary.initializing
        Write-Host "  running:" $workers.summary.running
        Write-Host "  throttled:" $workers.summary.throttled
        Write-Host "  unhealthy:" $workers.summary.unhealthy
    }

    $items = @()
    if ($workers.workers) { $items = @($workers.workers) }
    elseif ($workers.items) { $items = @($workers.items) }
    elseif ($workers.data) { $items = @($workers.data) }

    if ($items.Count -eq 0) {
        Write-Host "ACTIVE WORKERS: 0"
        Write-Host "Old worker cleanup: PASS"
    } else {
        Write-Host "ACTIVE WORKERS:" $items.Count
        foreach ($w in $items) {
            Write-Host (" - {0} status={1} stale={2} image={3}" -f `
                $w.id, $w.status, $w.isStale, $w.image)
        }
    }
}
catch {
    Write-Host "Worker list read failed:" $_.Exception.Message
    throw
}

Write-Host ""

$diskPass = ($diskGb -eq 40)

if ($diskPass) {
    Write-Host "40 GB disk verification: PASS"
} elseif ($null -eq $diskGb) {
    Write-Host "40 GB disk verification: UNKNOWN (API did not expose current value)"
} else {
    Write-Host "40 GB disk verification: FAIL (current value = $diskGb)"
}

Write-Host "Inference/TTS requests: 0"
Write-Host "GPU jobs submitted: 0"
Write-Host ""
Write-Host "NEXT: if disk=40 GB and old worker is cleared, run one fresh /health request."
