$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$envRuntime = Join-Path $root ".env.runtime"
$privateRoot = Join-Path $root "runtime\private\animation-studio\audio"
$outPath = Join-Path $privateRoot "kokoro-worker-contract.local.json"

$targetName = "miniverse-kokoro-tts-prod"
$restBase = "https://rest.runpod.io/v1"

Write-Host "=== STUDIO-006 KOKORO WORKER CONTRACT INSPECTION ==="
Write-Host "Target endpoint:" $targetName
Write-Host "Inference/TTS submissions: 0"
Write-Host "GPU jobs submitted: 0"
Write-Host "This step reads RunPod control-plane/template metadata only."
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

$headers = @{
    Authorization = "Bearer $apiKey"
    Accept = "application/json"
    "User-Agent" = "AHOS-STUDIO-006"
}

Write-Host "RUNPOD API KEY: PRESENT (hidden)"
Write-Host "Reading endpoint metadata..."

$endpoints = Invoke-RestMethod `
    -Uri "$restBase/endpoints?includeTemplate=true&includeWorkers=true" `
    -Method Get `
    -Headers $headers `
    -TimeoutSec 30

$matches = @($endpoints | Where-Object { $_.name -eq $targetName })
if ($matches.Count -ne 1) {
    throw "Expected exactly one endpoint named '$targetName', found $($matches.Count)."
}

$ep = $matches[0]
$endpointId = [string]$ep.id
$templateId = [string]$ep.templateId

if (-not $endpointId) { throw "Endpoint ID is empty." }
if (-not $templateId) { throw "Template ID is empty." }

Write-Host "Endpoint ID:" $endpointId
Write-Host "Template ID:" $templateId
Write-Host "Reading template metadata..."

$template = $null
$templateError = $null

try {
    $template = Invoke-RestMethod `
        -Uri "$restBase/templates/$templateId" `
        -Method Get `
        -Headers $headers `
        -TimeoutSec 30
}
catch {
    $templateError = $_.Exception.Message
}

# Direct endpoint read may expose a populated template object even if the
# template endpoint is unavailable for this account/template type.
$endpointDetail = $null
try {
    $endpointDetail = Invoke-RestMethod `
        -Uri "$restBase/endpoints/$endpointId?includeTemplate=true&includeWorkers=true" `
        -Method Get `
        -Headers $headers `
        -TimeoutSec 30
}
catch {}

if (-not $template -and $endpointDetail -and $endpointDetail.template) {
    $template = $endpointDetail.template
}

if (-not $template) {
    Write-Host "Template metadata could not be retrieved."
    if ($templateError) { Write-Host "Template read note:" $templateError }
    throw "Cannot inspect worker contract safely without template metadata."
}

$imageName = [string]$template.imageName
$templateName = [string]$template.name

$ports = @()
if ($template.ports) {
    if ($template.ports -is [string]) {
        $ports = @($template.ports -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    } else {
        $ports = @($template.ports)
    }
}

$portConfigs = @()
if ($template.portsConfig) {
    foreach ($pc in @($template.portsConfig)) {
        $portConfigs += [ordered]@{
            port = [string]$pc.port
            name = [string]$pc.name
        }
    }
}

$entrypoint = @()
if ($template.dockerEntrypoint) { $entrypoint = @($template.dockerEntrypoint) }

$startCmd = @()
if ($template.dockerStartCmd) { $startCmd = @($template.dockerStartCmd) }

$envKeys = @()
if ($template.env) {
    $envKeys = @($template.env.PSObject.Properties.Name | Sort-Object)
}

$readme = [string]$template.readme
$routeHints = New-Object System.Collections.Generic.HashSet[string]
if ($readme) {
    $patterns = @(
        '/health',
        '/healthz',
        '/docs',
        '/openapi.json',
        '/tts',
        '/synthesize',
        '/v1/audio/speech',
        '/v1/audio',
        '/audio/speech'
    )
    foreach ($p in $patterns) {
        if ($readme -match [regex]::Escape($p)) {
            [void]$routeHints.Add($p)
        }
    }
}

$invokeBase = "https://$endpointId.api.runpod.ai"

# Save only sanitized metadata; never save env values.
$sanitized = [ordered]@{
    schema = "ahos.kokoro-worker-contract.v1"
    endpoint = [ordered]@{
        id = $endpointId
        name = [string]$ep.name
        templateId = $templateId
        invokeBase = $invokeBase
        workersMin = $ep.workersMin
        workersMax = $ep.workersMax
        gpuCount = $ep.gpuCount
    }
    template = [ordered]@{
        id = [string]$template.id
        name = $templateName
        imageName = $imageName
        ports = $ports
        portsConfig = $portConfigs
        dockerEntrypoint = $entrypoint
        dockerStartCmd = $startCmd
        containerDiskInGb = $template.containerDiskInGb
        envKeys = $envKeys
        envValuesIncluded = $false
        routeHintsFromReadme = @($routeHints)
    }
    next = [ordered]@{
        liveRequestSent = $false
        contractKnownEnoughForLiveProbe = (
            [bool]$imageName -or
            $ports.Count -gt 0 -or
            $routeHints.Count -gt 0
        )
    }
}

New-Item -ItemType Directory -Force -Path $privateRoot | Out-Null
$sanitized | ConvertTo-Json -Depth 10 |
    Set-Content -Path $outPath -Encoding UTF8

Set-NonSecretEnv $envRuntime "RUNPOD_KOKORO_ENDPOINT_ID" $endpointId
Set-NonSecretEnv $envRuntime "RUNPOD_KOKORO_TEMPLATE_ID" $templateId
Set-NonSecretEnv $envRuntime "RUNPOD_KOKORO_INVOKE_BASE" $invokeBase

Write-Host ""
Write-Host "=== KOKORO WORKER CONTRACT INSPECTION PASS ==="
Write-Host "Endpoint:" $targetName
Write-Host "Endpoint ID:" $endpointId
Write-Host "Template ID:" $templateId
Write-Host "Invoke base:" $invokeBase
Write-Host "Template name:" $templateName

if ($imageName) {
    Write-Host "Container image:" $imageName
} else {
    Write-Host "Container image: not returned"
}

if ($ports.Count -gt 0) {
    Write-Host "Ports:" ($ports -join ", ")
} else {
    Write-Host "Ports: not returned"
}

if ($portConfigs.Count -gt 0) {
    Write-Host "Named ports:"
    foreach ($pc in $portConfigs) {
        Write-Host " -" $pc.port ":" $pc.name
    }
}

if ($entrypoint.Count -gt 0) {
    Write-Host "Entrypoint:" ($entrypoint -join " ")
}
if ($startCmd.Count -gt 0) {
    Write-Host "Start command:" ($startCmd -join " ")
}

Write-Host "Environment variable KEYS only:" $envKeys.Count
foreach ($key in $envKeys) {
    Write-Host " -" $key
}

if ($routeHints.Count -gt 0) {
    Write-Host "README route hints:"
    foreach ($route in $routeHints) {
        Write-Host " -" $route
    }
} else {
    Write-Host "README route hints: none detected"
}

Write-Host ""
Write-Host "Private sanitized contract:" $outPath
Write-Host "Environment values/secrets printed: NO"
Write-Host "Inference/TTS submissions: 0"
Write-Host "GPU jobs submitted: 0"
Write-Host ""
Write-Host "NEXT: use this exact contract to perform the smallest owner-approved live Kokoro probe."
