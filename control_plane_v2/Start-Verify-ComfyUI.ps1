$ErrorActionPreference = "Stop"

Write-Host "=== COMFYUI START + VERIFY ==="
Write-Host "Purpose: make STUDIO-005 visual pipeline actually reachable."
Write-Host "OpenAI/API spend: USD 0"
Write-Host ""

$endpoint = "http://127.0.0.1:8188"

function Test-ComfyUI {
    try {
        Invoke-RestMethod -Uri "$endpoint/system_stats" -Method Get -TimeoutSec 3 | Out-Null
        return $true
    } catch {
        return $false
    }
}

if (Test-ComfyUI) {
    Write-Host "COMFYUI ALREADY RUNNING: PASS"
    Write-Host "ENDPOINT: $endpoint"
    exit 0
}

$roots = @(
    "C:\Users\esmak",
    "C:\actions-runner"
) | Where-Object { Test-Path $_ }

$mainCandidates = @()
foreach ($root in $roots) {
    try {
        $mainCandidates += Get-ChildItem -Path $root -Filter "main.py" -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object {
                $_.FullName -match "\\ComfyUI\\main\.py$" -or
                $_.DirectoryName -match "ComfyUI"
            } |
            Select-Object -ExpandProperty FullName
    } catch {}
}

$mainCandidates = $mainCandidates | Sort-Object -Unique

if (-not $mainCandidates) {
    Write-Host "COMFYUI INSTALLATION: NOT FOUND"
    Write-Host "I searched:"
    $roots | ForEach-Object { Write-Host " - $_" }
    Write-Host ""
    Write-Host "Send me this screen. We will locate/reconnect the existing ComfyUI installation without reinstalling blindly."
    exit 2
}

$main = $mainCandidates[0]
$comfyRoot = Split-Path $main -Parent

Write-Host "COMFYUI FOUND:"
Write-Host $comfyRoot

$pythonCandidates = @(
    (Join-Path $comfyRoot "venv\Scripts\python.exe"),
    (Join-Path $comfyRoot ".venv\Scripts\python.exe"),
    (Join-Path (Split-Path $comfyRoot -Parent) "python_embeded\python.exe"),
    (Join-Path (Split-Path $comfyRoot -Parent) "python_embedded\python.exe")
) | Where-Object { Test-Path $_ }

if ($pythonCandidates.Count -gt 0) {
    $python = $pythonCandidates[0]
} else {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    $python = if ($cmd) { $cmd.Source } else { $null }
}

if (-not $python) {
    Write-Host "PYTHON FOR COMFYUI: NOT FOUND"
    Write-Host "ComfyUI root: $comfyRoot"
    exit 3
}

Write-Host "PYTHON:"
Write-Host $python
Write-Host ""
Write-Host "Starting ComfyUI on localhost:8188 ..."

$logRoot = "C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\control_plane_v2\runtime\private\animation-studio\comfyui"
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$stdout = Join-Path $logRoot "comfyui.stdout.log"
$stderr = Join-Path $logRoot "comfyui.stderr.log"

$proc = Start-Process `
    -FilePath $python `
    -ArgumentList @($main, "--listen", "127.0.0.1", "--port", "8188") `
    -WorkingDirectory $comfyRoot `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -PassThru

Write-Host "PID:" $proc.Id

$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 2
    if (Test-ComfyUI) {
        $ok = $true
        break
    }
    if ($proc.HasExited) {
        break
    }
}

if (-not $ok) {
    Write-Host ""
    Write-Host "COMFYUI START: FAILED"
    Write-Host "STDOUT: $stdout"
    Write-Host "STDERR: $stderr"
    if (Test-Path $stderr) {
        Write-Host ""
        Write-Host "Last error lines:"
        Get-Content $stderr -Tail 25 -ErrorAction SilentlyContinue
    }
    exit 4
}

Write-Host ""
Write-Host "=== COMFYUI READY ==="
Write-Host "COMFYUI REACHABLE: PASS"
Write-Host "ENDPOINT: $endpoint"

try {
    $info = Invoke-RestMethod -Uri "$endpoint/object_info" -Method Get -TimeoutSec 10
    $nodeCount = ($info.PSObject.Properties | Measure-Object).Count
    Write-Host "NODE COUNT:" $nodeCount
} catch {
    Write-Host "NODE INVENTORY: reachable, count unavailable"
}

Write-Host "OpenAI/API spend: USD 0"
Write-Host "No render job submitted."
