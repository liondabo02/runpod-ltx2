param(
    [int]$Port = 11500,
    [int]$IntervalSeconds = 45
)

# AHOS tünel bekçisi: port dinlemiyorsa SSH tünelini yeniden açar.
# Açılışta ve istenirse elle çalıştırılır; sonsuz döngüdür.
$key = Join-Path $env:USERPROFILE '.ssh\ahos-quality-99\oracle_ed25519'
$vm = 'ubuntu@130.61.35.81'
$log = Join-Path $env:TEMP 'ahos-tunnel-keeper.log'

function Write-Log([string]$Message) {
    $line = "{0} {1}" -f (Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'), $Message
    Add-Content -Path $log -Value $line -Encoding utf8
}

Write-Log "bekçi başladı (port $Port)"
while ($true) {
    $listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $listening) {
        try {
            Start-Process -FilePath 'ssh' -ArgumentList @(
                '-i', $key,
                '-N',
                '-o', 'ExitOnForwardFailure=yes',
                '-o', 'ServerAliveInterval=20',
                '-o', 'ServerAliveCountMax=3',
                '-o', 'TCPKeepAlive=yes',
                '-o', 'StrictHostKeyChecking=no',
                '-L', "${Port}:127.0.0.1:11434",
                $vm
            ) -WindowStyle Hidden
            Write-Log "tünel yeniden açıldı"
        } catch {
            Write-Log "tünel açılamadı: $($_.Exception.Message)"
        }
    }
    Start-Sleep -Seconds $IntervalSeconds
}
