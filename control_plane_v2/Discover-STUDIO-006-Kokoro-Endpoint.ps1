$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$envRuntime = Join-Path $root ".env.runtime"
$privateRoot = Join-Path $root "runtime\private\animation-studio\audio"
$outPath = Join-Path $privateRoot "kokoro-endpoint-discovery.local.json"

$targetName = "miniverse-kokoro-tts-prod"
$listUrl = "https://rest.runpod.io/v1/endpoints?includeTemplate=true&includeWorkers=true"

Write-Host "=== STUDIO-006 KOKORO ENDPOINT DISCOVERY ==="
Write-Host "Target endpoint:" $targetName
Write-Host "Inference/TTS submissions: 0"
Write-Host "GPU jobs submitted: 0"
Write-Host "This only reads RunPod control-plane metadata."
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

function Set-NonSecretEnv([string]$path, [string]$name, [string]$value) {
    $text = ""
    if (Test-Path $path) {
        $text = Get-Content $path -Raw -ErrorAction SilentlyContinue
        if ($null -eq $text) { $text = "" }
    }

    $pattern = "(?m)^$([regex]::Escape($name))=.*\r?\n?"
    $text = $text -replace $pattern, ""

    if ($text.Length -gt 0 -and -not $text.EndsWith("`n")) {
        $text += "`r`n"
    }
    $text += "$name=$value`r`n"

    [IO.File]::WriteAllText($path, $text, [Text.UTF8Encoding]::new($false))
}

$apiKey = $env:RUNPOD_API_KEY
if (-not $apiKey) {
    $apiKey = Get-EnvValue $envRuntime "RUNPOD_API_KEY"
}
if (-not $apiKey) {
    throw "RUNPOD_API_KEY was not found in environment or .env.runtime."
}

Write-Host "RUNPOD API KEY: PRESENT (hidden)"

$headers = @{
    Authorization = "Bearer $apiKey"
    Accept = "application/json"
    "User-Agent" = "AHOS-STUDIO-006"
}

try {
    $all = Invoke-RestMethod `
        -Uri $listUrl `
        -Method Get `
        -Headers $headers `
        -TimeoutSec 30
}
catch {
    $statusCode = $null
    try { $statusCode = [int]$_.Exception.Response.StatusCode } catch {}
    if ($statusCode) { Write-Host "HTTP STATUS:" $statusCode }
    throw "RunPod endpoint discovery failed: $($_.Exception.Message)"
}

$matches = @($all | Where-Object { $_.name -eq $targetName })

if ($matches.Count -eq 0) {
    Write-Host ""
    Write-Host "TARGET ENDPOINT NOT FOUND."
    Write-Host "Available endpoint names:"
    $all | ForEach-Object { Write-Host " -" $_.name }
    throw "Could not find exact endpoint name '$targetName'."
}

if ($matches.Count -gt 1) {
    throw "More than one endpoint named '$targetName' was found."
}

$ep = $matches[0]
$endpointId = [string]$ep.id
if ([string]::IsNullOrWhiteSpace($endpointId)) {
    throw "Endpoint was found but id is empty."
}

$template = $ep.template
$imageName = $null
$dockerStartCmd = $null
$ports = $null
$containerDiskGb = $null

if ($template) {
    if ($template.PSObject.Properties.Name -contains "imageName") {
        $imageName = $template.imageName
    }
    if ($template.PSObject.Properties.Name -contains "dockerStartCmd") {
        $dockerStartCmd = $template.dockerStartCmd
    }
    if ($template.PSObject.Properties.Name -contains "ports") {
        $ports = $template.ports
    }
    if ($template.PSObject.Properties.Name -contains "containerDiskInGb") {
        $containerDiskGb = $template.containerDiskInGb
    }
}

$invokeBase = "https://$endpointId.api.runpod.ai"

$sanitized = [ordered]@{
    schema = "ahos.kokoro-endpoint-discovery.v1"
    endpoint = [ordered]@{
        id = $endpointId
        name = [string]$ep.name
        templateId = [string]$ep.templateId
        workersMin = $ep.workersMin
        workersMax = $ep.workersMax
        gpuCount = $ep.gpuCount
        idleTimeout = $ep.idleTimeout
        executionTimeoutMs = $ep.executionTimeoutMs
        computeType = $ep.computeType
        gpuTypeIds = @($ep.gpuTypeIds)
        invokeBase = $invokeBase
    }
    template_safe = [ordered]@{
        imageName = $imageName
        dockerStartCmd = $dockerStartCmd
        ports = $ports
        containerDiskInGb = $containerDiskGb
        environment_values_included = $false
    }
    invocation = [ordered]@{
        endpoint_type_observed_in_console = "load_balancer"
        no_live_request_sent = $true
        next_step = "inspect worker contract and determine safe health/TTS path"
    }
}

New-Item -ItemType Directory -Force -Path $privateRoot | Out-Null
$sanitized | ConvertTo-Json -Depth 8 |
    Set-Content -Path $outPath -Encoding UTF8

Set-NonSecretEnv $envRuntime "RUNPOD_KOKORO_ENDPOINT_ID" $endpointId
Set-NonSecretEnv $envRuntime "RUNPOD_KOKORO_ENDPOINT_NAME" $targetName
Set-NonSecretEnv $envRuntime "AHOS_TTS_EXECUTION_ENABLED" "false"
Set-NonSecretEnv $envRuntime "AHOS_PAID_TTS_ENABLED" "false"

Write-Host ""
Write-Host "=== KOKORO ENDPOINT DISCOVERY PASS ==="
Write-Host "Endpoint name:" $targetName
Write-Host "Endpoint ID:" $endpointId
Write-Host "Invoke base:" $invokeBase
Write-Host "Workers min/max:" $ep.workersMin "/" $ep.workersMax
Write-Host "GPU count:" $ep.gpuCount
if ($imageName) {
    Write-Host "Container image:" $imageName
} else {
    Write-Host "Container image: not returned by this control-plane read"
}
if ($ports) {
    Write-Host "Exposed ports:" ($ports -join ", ")
}
Write-Host ""
Write-Host "Private metadata saved:" $outPath
Write-Host "Environment values/secrets printed: NO"
Write-Host "Inference/TTS submissions: 0"
Write-Host "GPU jobs submitted: 0"
Write-Host ""
Write-Host "NEXT: inspect the Kokoro worker contract, then perform the smallest safe live health/TTS verification."
