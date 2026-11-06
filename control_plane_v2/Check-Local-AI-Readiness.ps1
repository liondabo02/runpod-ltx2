$ErrorActionPreference = 'Stop'

function Format-GB([double]$bytes) {
    return [math]::Round($bytes / 1GB, 2)
}

Write-Host "=== MINIVERSE LOCAL AI READINESS ==="
Write-Host ""

$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$cs = Get-CimInstance Win32_ComputerSystem
$os = Get-CimInstance Win32_OperatingSystem
$gpus = Get-CimInstance Win32_VideoController
$drive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"

$ramGb = Format-GB([double]$cs.TotalPhysicalMemory)
$freeRamGb = Format-GB([double]$os.FreePhysicalMemory * 1KB)
$diskFreeGb = if ($drive) { Format-GB([double]$drive.FreeSpace) } else { 0 }

Write-Host "CPU: $($cpu.Name)"
Write-Host "Logical processors: $($cpu.NumberOfLogicalProcessors)"
Write-Host "RAM total: $ramGb GB"
Write-Host "RAM free now: $freeRamGb GB"
Write-Host "C: free space: $diskFreeGb GB"
Write-Host ""
Write-Host "GPU(s):"
foreach ($gpu in $gpus) {
    $adapterGb = if ($gpu.AdapterRAM) { Format-GB([double]$gpu.AdapterRAM) } else { 'unknown' }
    Write-Host " - $($gpu.Name) | reported VRAM: $adapterGb GB"
}

$nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
$nvidiaVramGb = $null
if ($nvidiaSmi) {
    try {
        $rows = & nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader,nounits 2>$null
        if ($LASTEXITCODE -eq 0 -and $rows) {
            Write-Host ""
            Write-Host "NVIDIA detail:"
            foreach ($row in $rows) {
                $parts = $row -split ',' | ForEach-Object { $_.Trim() }
                if ($parts.Count -ge 3) {
                    $totalMiB = [double]$parts[1]
                    $freeMiB = [double]$parts[2]
                    $totalGb = [math]::Round($totalMiB / 1024, 2)
                    $freeGb = [math]::Round($freeMiB / 1024, 2)
                    Write-Host " - $($parts[0]) | VRAM total: $totalGb GB | free: $freeGb GB"
                    if ($null -eq $nvidiaVramGb -or $totalGb -gt $nvidiaVramGb) {
                        $nvidiaVramGb = $totalGb
                    }
                }
            }
        }
    } catch {
        Write-Host "NVIDIA detail: unavailable"
    }
}

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
Write-Host ""
if ($ollama) {
    Write-Host "Ollama: INSTALLED ($($ollama.Source))"
    try {
        $models = & ollama list 2>$null
        if ($models) {
            Write-Host "Installed local models:"
            $models | ForEach-Object { Write-Host " $_" }
        }
    } catch {}
} else {
    Write-Host "Ollama: NOT INSTALLED"
}

Write-Host ""
Write-Host "=== RECOMMENDATION ==="

if ($nvidiaVramGb -ge 16) {
    Write-Host "Tier: STRONG LOCAL AI"
    Write-Host "Recommended target: 14B-32B quantized coding models, depending on speed/quality preference."
} elseif ($nvidiaVramGb -ge 8) {
    Write-Host "Tier: GOOD LOCAL AI"
    Write-Host "Recommended target: 7B-14B quantized coding models."
} elseif ($nvidiaVramGb -ge 4) {
    Write-Host "Tier: LIGHT LOCAL AI"
    Write-Host "Recommended target: small 3B-7B quantized coding models; use OpenAI for harder tasks."
} elseif ($ramGb -ge 32) {
    Write-Host "Tier: CPU/RAM LOCAL AI"
    Write-Host "Recommended target: small 3B-7B quantized coding models on CPU/RAM; slower but API-free."
} elseif ($ramGb -ge 16) {
    Write-Host "Tier: VERY LIGHT LOCAL AI"
    Write-Host "Recommended target: 1.5B-3B coding model for cheap local triage; OpenAI for real coding work."
} else {
    Write-Host "Tier: LOCAL AI NOT RECOMMENDED FOR AUTONOMOUS CODING"
    Write-Host "Use free deterministic checks first, then OpenAI only when needed."
}

if ($diskFreeGb -lt 20) {
    Write-Host "WARNING: Less than 20 GB free on C:. Local models may not fit comfortably."
}

Write-Host ""
Write-Host "This check makes NO OpenAI API calls and costs $0 in API usage."
