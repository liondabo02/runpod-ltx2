$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$envRuntime = Join-Path $root ".env.runtime"
$privateRoot = Join-Path $root "runtime\private\animation-studio\audio"
$outPath = Join-Path $privateRoot "kokoro-worker-contract.local.json"

$targetName = "miniverse-kokoro-tts-prod"
$restBase = "https://rest.runpod.io/v1"
$graphqlUrl = "https://api.runpod.io/graphql"

Write-Host "=== STUDIO-006 KOKORO CONTRACT RECOVERY V2 ==="
Write-Host "Fix: re-read endpoint + template ID, persist them, then use GraphQL fallback."
Write-Host "Inference/TTS submissions: 0"
Write-Host "GPU jobs submitted: 0"
Write-Host "Paid inference spend: USD 0"
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
    "Content-Type" = "application/json"
    "User-Agent" = "AHOS-STUDIO-006"
}

Write-Host "RUNPOD API KEY: PRESENT (hidden)"
Write-Host "Refreshing endpoint metadata..."

$endpoints = Invoke-RestMethod `
    -Uri "$restBase/endpoints?includeTemplate=true&includeWorkers=true" `
    -Method Get `
    -Headers $headers `
    -TimeoutSec 30

$matches = @($endpoints | Where-Object { $_.name -eq $targetName })

if ($matches.Count -eq 0) {
    Write-Host "Available endpoint names:"
    $endpoints | ForEach-Object { Write-Host " -" $_.name }
    throw "Endpoint '$targetName' was not found."
}

if ($matches.Count -gt 1) {
    throw "More than one endpoint named '$targetName' was found."
}

$ep = $matches[0]
$endpointId = [string]$ep.id
$templateId = [string]$ep.templateId

if ([string]::IsNullOrWhiteSpace($endpointId)) {
    throw "Endpoint ID is empty."
}
if ([string]::IsNullOrWhiteSpace($templateId)) {
    throw "Template ID is empty in RunPod endpoint metadata."
}

# Persist the non-secret IDs so future steps do not depend on this shell.
Set-NonSecretEnv $envRuntime "RUNPOD_KOKORO_ENDPOINT_ID" $endpointId
Set-NonSecretEnv $envRuntime "RUNPOD_KOKORO_TEMPLATE_ID" $templateId
Set-NonSecretEnv $envRuntime "RUNPOD_KOKORO_ENDPOINT_NAME" $targetName

Write-Host "Endpoint ID:" $endpointId
Write-Host "Template ID:" $templateId
Write-Host "Saved non-secret IDs to .env.runtime"
Write-Host ""
Write-Host "Reading template through GraphQL fallback..."

$query = @'
query GetTemplate($id: String!) {
  podTemplate(id: $id) {
    id
    name
    imageName
    isServerless
    isPublic
    isRunpod
    category
    ports
    portsConfig {
      port
      name
    }
    env {
      key
      value
    }
    containerDiskInGb
    containerRegistryAuthId
    volumeInGb
    volumeMountPath
    readme
  }
}
'@

$body = @{
    query = $query
    variables = @{
        id = $templateId
    }
} | ConvertTo-Json -Depth 8

$response = Invoke-RestMethod `
    -Uri $graphqlUrl `
    -Method Post `
    -Headers $headers `
    -Body $body `
    -TimeoutSec 30

if ($response.errors) {
    $messages = @($response.errors | ForEach-Object { $_.message })
    throw ("RunPod GraphQL returned errors: " + ($messages -join " | "))
}

$template = $response.data.podTemplate
if (-not $template) {
    throw "GraphQL returned no podTemplate for ID $templateId."
}

$imageName = [string]$template.imageName
$templateName = [string]$template.name
$category = [string]$template.category

$ports = @()
if ($template.ports) {
    if ($template.ports -is [string]) {
        $ports = @(
            $template.ports -split "," |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ }
        )
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

$envKeys = @()
if ($template.env) {
    foreach ($pair in @($template.env)) {
        if ($pair.key) {
            $envKeys += [string]$pair.key
        }
    }
    $envKeys = @($envKeys | Sort-Object -Unique)
}

$readme = [string]$template.readme
$routeHints = New-Object System.Collections.Generic.HashSet[string]

if ($readme) {
    $knownRoutes = @(
        "/health",
        "/healthz",
        "/docs",
        "/openapi.json",
        "/tts",
        "/synthesize",
        "/generate",
        "/v1/audio/speech",
        "/audio/speech"
    )

    foreach ($route in $knownRoutes) {
        if ($readme -match [regex]::Escape($route)) {
            [void]$routeHints.Add($route)
        }
    }

    $matches2 = [regex]::Matches(
        $readme,
        '(?<![A-Za-z0-9])/(?:[A-Za-z0-9._~-]+/?){1,4}'
    )

    foreach ($m in $matches2) {
        $candidate = $m.Value.TrimEnd(".",";",",",")","]","}")
        if (
            $candidate.Length -le 80 -and
            $candidate -notmatch '^/(usr|bin|opt|tmp|var|home|workspace|runpod-volume)'
        ) {
            [void]$routeHints.Add($candidate)
        }
    }
}

$invokeBase = "https://$endpointId.api.runpod.ai"
Set-NonSecretEnv $envRuntime "RUNPOD_KOKORO_INVOKE_BASE" $invokeBase

$sanitized = [ordered]@{
    schema = "ahos.kokoro-worker-contract.v2"
    endpoint = [ordered]@{
        id = $endpointId
        name = $targetName
        templateId = $templateId
        invokeBase = $invokeBase
        endpointTypeObserved = "load_balancer"
        workersMin = $ep.workersMin
        workersMax = $ep.workersMax
        gpuCount = $ep.gpuCount
    }
    template = [ordered]@{
        id = [string]$template.id
        name = $templateName
        imageName = $imageName
        category = $category
        isServerless = [bool]$template.isServerless
        isPublic = [bool]$template.isPublic
        isRunpod = [bool]$template.isRunpod
        ports = $ports
        portsConfig = $portConfigs
        containerDiskInGb = $template.containerDiskInGb
        volumeInGb = $template.volumeInGb
        volumeMountPath = [string]$template.volumeMountPath
        envKeys = $envKeys
        envValuesIncluded = $false
        routeHintsFromReadme = @($routeHints | Sort-Object)
        readmeStored = $false
    }
    safety = [ordered]@{
        inferenceRequestSent = $false
        gpuJobSubmitted = $false
        secretValuesStored = $false
    }
}

New-Item -ItemType Directory -Force -Path $privateRoot | Out-Null
$sanitized | ConvertTo-Json -Depth 12 |
    Set-Content -Path $outPath -Encoding UTF8

Write-Host ""
Write-Host "=== KOKORO CONTRACT RECOVERY V2 PASS ==="
Write-Host "Endpoint name:" $targetName
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

Write-Host "Environment variable KEYS only:" $envKeys.Count
foreach ($key in $envKeys) {
    Write-Host " -" $key
}

if ($routeHints.Count -gt 0) {
    Write-Host "README route hints:"
    foreach ($route in @($routeHints | Sort-Object)) {
        Write-Host " -" $route
    }
} else {
    Write-Host "README route hints: none detected"
}

Write-Host ""
Write-Host "Sanitized private contract:" $outPath
Write-Host "Environment values/secrets printed: NO"
Write-Host "Inference/TTS submissions: 0"
Write-Host "GPU jobs submitted: 0"
Write-Host "Paid inference spend: USD 0"
Write-Host ""
Write-Host "NEXT: smallest owner-approved live Kokoro probe using this exact contract."
