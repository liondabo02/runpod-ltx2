$ErrorActionPreference = "Continue"

Write-Host "=== FIND EXISTING COMFYUI INSTALLATION ==="
Write-Host "No install/change/render will be performed."
Write-Host "OpenAI/API spend: USD 0"
Write-Host ""

$found = New-Object System.Collections.Generic.List[string]

function Add-Candidate([string]$path) {
    if ([string]::IsNullOrWhiteSpace($path)) { return }
    try {
        $full = [IO.Path]::GetFullPath($path)
        if ((Test-Path $full) -and (-not $found.Contains($full))) {
            $found.Add($full)
        }
    } catch {}
}

# 1) Very common install locations first.
$common = @(
    "$env:USERPROFILE\ComfyUI",
    "$env:USERPROFILE\Desktop\ComfyUI",
    "$env:USERPROFILE\Downloads\ComfyUI",
    "$env:USERPROFILE\Documents\ComfyUI",
    "$env:LOCALAPPDATA\ComfyUI",
    "$env:APPDATA\ComfyUI",
    "C:\ComfyUI",
    "C:\AI\ComfyUI",
    "C:\StableDiffusion\ComfyUI",
    "C:\ComfyUI_windows_portable\ComfyUI",
    "D:\ComfyUI",
    "D:\AI\ComfyUI",
    "D:\ComfyUI_windows_portable\ComfyUI",
    "E:\ComfyUI",
    "E:\AI\ComfyUI",
    "E:\ComfyUI_windows_portable\ComfyUI"
)
foreach ($c in $common) {
    if (Test-Path (Join-Path $c "main.py")) { Add-Candidate $c }
}

# 2) Search every fixed/local filesystem drive for ComfyUI folders.
$drives = Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Root -match "^[A-Z]:\\$" }

foreach ($drive in $drives) {
    Write-Host "Searching drive $($drive.Root) ..."
    try {
        $dirs = Get-ChildItem -Path $drive.Root -Directory -Filter "ComfyUI" -Recurse -Force -ErrorAction SilentlyContinue
        foreach ($dir in $dirs) {
            if (Test-Path (Join-Path $dir.FullName "main.py")) {
                Add-Candidate $dir.FullName
            }
        }
    } catch {}
}

# 3) Look for portable launcher files too.
$portableRoots = New-Object System.Collections.Generic.List[string]
foreach ($drive in $drives) {
    try {
        $launchers = Get-ChildItem -Path $drive.Root -File -Filter "run_nvidia_gpu.bat" -Recurse -Force -ErrorAction SilentlyContinue
        foreach ($launcher in $launchers) {
            $parent = Split-Path $launcher.FullName -Parent
            $candidate = Join-Path $parent "ComfyUI"
            if (Test-Path (Join-Path $candidate "main.py")) {
                Add-Candidate $candidate
                if (-not $portableRoots.Contains($parent)) { $portableRoots.Add($parent) }
            }
        }
    } catch {}
}

Write-Host ""
if ($found.Count -eq 0) {
    Write-Host "=== RESULT ==="
    Write-Host "COMFYUI INSTALLATION: NOT FOUND ON LOCAL FILESYSTEM DRIVES"
    Write-Host ""
    Write-Host "This means the old ComfyUI folder is either:"
    Write-Host " - deleted,"
    Write-Host " - on an unmounted/external drive,"
    Write-Host " - inside WSL/Docker,"
    Write-Host " - or installed under a nonstandard environment not visible as a normal ComfyUI folder."
    Write-Host ""
    Write-Host "Send me this result. Do NOT reinstall anything yet."
    exit 2
}

Write-Host "=== RESULT ==="
Write-Host "COMFYUI CANDIDATES FOUND:" $found.Count
for ($i = 0; $i -lt $found.Count; $i++) {
    Write-Host "[$($i+1)] $($found[$i])"
    $main = Join-Path $found[$i] "main.py"
    Write-Host "    main.py: $main"

    $parent = Split-Path $found[$i] -Parent
    $embedded1 = Join-Path $parent "python_embeded\python.exe"
    $embedded2 = Join-Path $parent "python_embedded\python.exe"
    $venv1 = Join-Path $found[$i] "venv\Scripts\python.exe"
    $venv2 = Join-Path $found[$i] ".venv\Scripts\python.exe"

    if (Test-Path $embedded1) { Write-Host "    python: $embedded1" }
    elseif (Test-Path $embedded2) { Write-Host "    python: $embedded2" }
    elseif (Test-Path $venv1) { Write-Host "    python: $venv1" }
    elseif (Test-Path $venv2) { Write-Host "    python: $venv2" }
    else { Write-Host "    python: not detected beside installation" }
}

Write-Host ""
Write-Host "No ComfyUI process was started."
Write-Host "No files were changed."
Write-Host "No API money was spent."
