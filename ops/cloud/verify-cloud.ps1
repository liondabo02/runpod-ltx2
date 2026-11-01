# Bulut bağlantısını tek komutta doğrular.
# Kullanım: powershell -NoProfile -ExecutionPolicy Bypass -File ops\cloud\verify-cloud.ps1
param(
    [string]$Target = 'ubuntu@130.61.35.81',
    [int]$RemoteModelPort = 11500,
    [int]$LocalOllamaPort = 11434,
    [int]$PanelPort = 8766
)

$ErrorActionPreference = 'Continue'
$ssh = 'C:\Windows\System32\OpenSSH\ssh.exe'
if (-not (Test-Path $ssh)) { $ssh = 'ssh' }
$KeyPath = 'C:\Users\esmak\.ssh\ahos-quality-99\oracle_ed25519'

"== 1. Yerel panel (Windows) =="
try {
    $local = & curl.exe -s "http://127.0.0.1:$PanelPort/api/status"
    if ($local) { "   yerel panel: OK (" + $local.Length + " bayt)" } else { "   yerel panel: yanit yok" }
} catch { "   yerel panel: HATA" }

"== 2. Ters tunel kuruluyor ($RemoteModelPort -> 127.0.0.1:$LocalOllamaPort) =="
$tunnel = Start-Process -FilePath $ssh -ArgumentList @(
    '-N','-o','ExitOnForwardFailure=yes','-o','ServerAliveInterval=20',
    '-o','StrictHostKeyChecking=accept-new',
    '-i', $KeyPath, '-o', 'IdentitiesOnly=yes',
    '-R', "${RemoteModelPort}:127.0.0.1:${LocalOllamaPort}", $Target
) -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 5
if ($tunnel.HasExited) { "   tunel KURULAMADI (exit $($tunnel.ExitCode)); port kullanimda olabilir" }
else { "   tunel acik (pid $($tunnel.Id))" }

"== 3. Sunucuda model ve panel kontrolu =="
& $ssh -i $KeyPath -o IdentitiesOnly=yes $Target "curl -s http://127.0.0.1:${RemoteModelPort}/api/tags | head -c 120; echo; curl -s http://127.0.0.1:${PanelPort}/api/status | head -c 120; echo"

"== 3b. Sunucudaki servisler =="
& $ssh -i $KeyPath -o IdentitiesOnly=yes $Target "systemctl is-active ahos-panel ahos-worker; sudo -n systemctl start ahos-worker 2>/dev/null; systemctl is-active ahos-worker"

"== 4. Ozet =="
if (-not $tunnel.HasExited) {
    "   Bulut paneli: ssh -L ${PanelPort}:127.0.0.1:${PanelPort} $Target  ->  http://127.0.0.1:${PanelPort}/"
    "   Tunel bu betik kapaninca duser; kalici olsun diye Startup\AHOS-ReverseTunnel.cmd kullan."
}
