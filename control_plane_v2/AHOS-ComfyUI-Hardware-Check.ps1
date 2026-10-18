$ErrorActionPreference = "SilentlyContinue"

Write-Host "=== AHOS COMFYUI HARDWARE CHECK ==="
Write-Host "No installation or changes will be made."
Write-Host ""

Write-Host "WINDOWS:"
Get-CimInstance Win32_OperatingSystem |
    Select-Object Caption, Version, OSArchitecture |
    Format-List

Write-Host "CPU:"
Get-CimInstance Win32_Processor |
    Select-Object Name, NumberOfCores, NumberOfLogicalProcessors |
    Format-List

Write-Host "RAM:"
$os = Get-CimInstance Win32_OperatingSystem
$ramGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
Write-Host "Total RAM GB:" $ramGB
Write-Host ""

Write-Host "GPU:"
$gpus = Get-CimInstance Win32_VideoController
$gpus | Select-Object Name, AdapterRAM, DriverVersion | Format-Table -AutoSize

$nvidia = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
if ($nvidia) {
    Write-Host ""
    Write-Host "NVIDIA-SMI:"
    & $nvidia.Source --query-gpu=name,memory.total,driver_version,compute_cap --format=csv,noheader
} else {
    Write-Host ""
    Write-Host "NVIDIA-SMI: NOT FOUND"
}

Write-Host ""
Write-Host "DISK:"
Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" |
    Select-Object DeviceID,
        @{N="FreeGB";E={[math]::Round($_.FreeSpace/1GB,1)}},
        @{N="TotalGB";E={[math]::Round($_.Size/1GB,1)}} |
    Format-Table -AutoSize

Write-Host ""
Write-Host "PYTHON:"
$py = Get-Command python.exe -ErrorAction SilentlyContinue
if ($py) {
    Write-Host "Path:" $py.Source
    & $py.Source --version
} else {
    Write-Host "NOT FOUND"
}

Write-Host ""
Write-Host "GIT:"
$git = Get-Command git.exe -ErrorAction SilentlyContinue
if ($git) {
    Write-Host "Path:" $git.Source
    & $git.Source --version
} else {
    Write-Host "NOT FOUND"
}

Write-Host ""
Write-Host "=== CHECK COMPLETE ==="
Write-Host "Send me this final screen."
Write-Host "No files changed. No API/render cost."
