# Oracle bulut paneli için ters tünel bekçisi.
# Sunucudaki 127.0.0.1:11500 → bu Windows makinesindeki Ollama (11434).
# Kullanım: powershell -NoProfile -ExecutionPolicy Bypass -File ops\tunnel\keep-reverse-tunnel.ps1
# Not: Bu pencere açık kaldığı sürece bulut paneli modele erişir.
param(
    [string]$Target = 'ubuntu@130.61.35.81',
    [int]$RemotePort = 11500,
    [int]$LocalPort = 11434,
    [int]$RetrySeconds = 20
)

$ErrorActionPreference = 'Continue'
$ssh = 'C:\Windows\System32\OpenSSH\ssh.exe'
if (-not (Test-Path $ssh)) { $ssh = 'ssh' }

while ($true) {
    $stamp = (Get-Date).ToString('HH:mm:ss')
    "[$stamp] ters tunel kuruluyor: ${RemotePort} -> 127.0.0.1:${LocalPort}"
    $args = @(
        '-N',
        '-o', 'ExitOnForwardFailure=yes',
        '-o', 'ServerAliveInterval=20',
        '-o', 'ServerAliveCountMax=3',
        '-o', 'StrictHostKeyChecking=accept-new',
        '-i', 'C:\Users\esmak\.ssh\ahos-quality-99\oracle_ed25519',
        '-o', 'IdentitiesOnly=yes',
        '-R', "${RemotePort}:127.0.0.1:${LocalPort}",
        $Target
    )
    $process = Start-Process -FilePath $ssh -ArgumentList $args -PassThru -WindowStyle Hidden
    $process.WaitForExit()
    "[$stamp] tunel kapandi (exit $($process.ExitCode)); ${RetrySeconds}s sonra tekrar"
    Start-Sleep -Seconds $RetrySeconds
}
