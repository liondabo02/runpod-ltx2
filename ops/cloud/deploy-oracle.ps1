# AHOS'u Oracle bulut sunucusuna taşır (tek komut).
# Kullanım (Windows PowerShell):
#   powershell -NoProfile -ExecutionPolicy Bypass -File ops\cloud\deploy-oracle.ps1
# Ön koşul: `ssh oracle` çalışıyor olmalı (anahtar ~/.ssh/config içinde tanımlı).
#
# Ne yapar:
#   1) ahos_core + control_plane_v2 betiklerini sunucuya kopyalar
#   2) python3 venv kurar (AHOS stdlib tabanlıdır, ek bağımlılık yok)
#   3) iki systemd servisi kurar: ahos-panel (8766) ve ahos-worker (Ruflo kuyruğu)
#   4) servisleri başlatır ve sağlık kontrolü yapar
#
# Geri alma:  ssh oracle "sudo systemctl disable --now ahos-panel ahos-worker; sudo rm -f /etc/systemd/system/ahos-panel.service /etc/systemd/system/ahos-worker.service"
param(
    [string]$Host_ = 'oracle',
    [string]$RemoteRoot = '/opt/ahos',
    [int]$Port = 8766,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
# $PSScriptRoot = <repo>\ops\cloud  →  iki üst dizin = <repo>
$ScriptDir = $PSScriptRoot
$OpsDir = Split-Path -Parent $ScriptDir
$Repo = Split-Path -Parent $OpsDir

function Invoke-Remote([string]$Command) {
    if ($DryRun) { "DRY: $Command"; return }
    & ssh $Host_ $Command
    if ($LASTEXITCODE -ne 0) { throw "uzak komut başarısız: $Command" }
}

"== 1. Paket hazırlanıyor =="
$stage = Join-Path $env:TEMP 'ahos-cloud-stage'
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Path (Join-Path $stage 'ahos') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stage 'ops') -Force | Out-Null
Copy-Item (Join-Path $Repo 'ahos_core\ahos\*') (Join-Path $stage 'ahos') -Recurse -Force
Copy-Item (Join-Path $Repo 'ahos_core\pyproject.toml') $stage -ErrorAction SilentlyContinue
Copy-Item (Join-Path $Repo 'ops\*') (Join-Path $stage 'ops') -Recurse -Force
"   staged: $stage"

"== 2. Sunucuya kopyalanıyor =="
Invoke-Remote "sudo mkdir -p $RemoteRoot && sudo chown -R `$USER`:`$USER` $RemoteRoot"
if (-not $DryRun) {
    & scp -r "$stage\*" "${Host_}:$RemoteRoot/"
    if ($LASTEXITCODE -ne 0) { throw 'scp başarısız' }
}

"== 3. Python venv + servisler =="
$panelUnit = @"
[Unit]
Description=AHOS Holding Panel ($Port)
After=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$RemoteRoot
Environment=AHOS_RUNTIME_DIR=$RemoteRoot/runtime
Environment=AHOS_LLM_BASE_URL=http://127.0.0.1:11500/v1
Environment=AHOS_LLM_MODEL=qwen2.5-coder:7b
Environment=AHOS_LLM_FREE=1
Environment=AHOS_ALLOW_PAID_LLM=0
ExecStart=/usr/bin/python3 -m ahos.control_center --runtime-dir $RemoteRoot/runtime --host 127.0.0.1 --port $Port
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"@
Set-Content -Path (Join-Path $stage 'ahos-panel.service') -Value $panelUnit -Encoding utf8

$workerUnit = @"
[Unit]
Description=AHOS Ruflo queue worker
After=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$RemoteRoot
Environment=AHOS_RUNTIME_DIR=$RemoteRoot/runtime
ExecStart=/usr/bin/python3 -m ahos.daemon --runtime-dir $RemoteRoot/runtime --executor-mode deterministic --missions-per-hour 6
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"@
Set-Content -Path (Join-Path $stage 'ahos-worker.service') -Value $workerUnit -Encoding utf8

if (-not $DryRun) {
    & scp (Join-Path $stage 'ahos-panel.service') "${Host_}:/tmp/ahos-panel.service"
    & scp (Join-Path $stage 'ahos-worker.service') "${Host_}:/tmp/ahos-worker.service"
}

Invoke-Remote "sudo mv /tmp/ahos-panel.service /tmp/ahos-worker.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now ahos-panel ahos-worker"
Invoke-Remote "mkdir -p $RemoteRoot/runtime"

"== 4. Sağlık kontrolü =="
if ($DryRun) { "DRY: ssh $Host_ 'curl -fsS http://127.0.0.1:$Port/api/status | head -c 200'" } else {
    & ssh $Host_ "sleep 3; curl -fsS http://127.0.0.1:$Port/api/status | head -c 300"
    if ($LASTEXITCODE -ne 0) { throw 'panel sağlık kontrolü başarısız (journalctl -u ahos-panel)' }
}

@"
Bulut kurulumu tamam.

Panel erişimi (kendi makineden güvenli tünel):
  ssh -L ${Port}:127.0.0.1:${Port} $Host_
  tarayıcı: http://127.0.0.1:$Port/

Servisler:
  ssh $Host_ 'sudo systemctl status ahos-panel ahos-worker --no-pager'
  ssh $Host_ 'sudo journalctl -u ahos-panel -n 50 --no-pager'

Model: tünel (11500) yoksa sunucuda yerel ollama kurulmalı:
  ssh $Host_ 'curl -fsSL https://ollama.com/install.sh | sh && ollama pull qwen2.5-coder:7b'
"@ | Write-Output
