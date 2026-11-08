# AHOS haftalık ritmi Windows Görev Zamanlayıcısı'na kaydeder.
#
#   .\Register-AHOS-Cadence.ps1 -Mode register [-Time 07:00]
#   .\Register-AHOS-Cadence.ps1 -Mode status
#   .\Register-AHOS-Cadence.ps1 -Mode remove
#
# Kayıt, günlük olarak `ahos-cadence --once` çalıştırır. Ritim görev bazlıdır:
# aynı hafta içinde ikinci kez açılmaz (idempotent), yani günlük çalışması
# zararsızdır ve haftalık planı otomatik başlatır.

[CmdletBinding()]
param(
    [ValidateSet('register', 'remove', 'status')]
    [string]$Mode = 'status',
    [string]$Time = '07:00',
    [string]$TaskName = 'AHOS-Cadence',
    [string]$RuntimeDir = ''
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo 'control_plane_v2\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Python bulunamadi: $python"
}
if (-not $RuntimeDir) {
    $RuntimeDir = Join-Path $repo 'ahos_core\runtime'
}
$logDir = Join-Path $RuntimeDir 'reports'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir 'cadence.log'

switch ($Mode) {
    'register' {
        $cmdLine = "set PYTHONIOENCODING=utf-8&& `"$python`" -m ahos.ops_cadence --once --runtime-dir `"$RuntimeDir`" >> `"$logFile`" 2>&1"
        $taskAction = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c $cmdLine" `
            -WorkingDirectory (Join-Path $repo 'ahos_core')
        $taskTrigger = New-ScheduledTaskTrigger -Daily -At $Time
        $taskSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries `
            -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
        Register-ScheduledTask -TaskName $TaskName -Action $taskAction -Trigger $taskTrigger `
            -Settings $taskSettings -Description 'AHOS haftalik departman ritmi' -Force | Out-Null
        Write-Output "Kaydedildi: $TaskName (gunluk $Time)"
    }
    'remove' {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
        Write-Output "Kaldirildi: $TaskName"
    }
    'status' {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($null -eq $task) {
            Write-Output "Kayitli degil: $TaskName"
        }
        else {
            $info = Get-ScheduledTaskInfo -TaskName $TaskName
            Write-Output ("Durum: {0} | son calisma: {1} | son sonuc: {2}" -f `
                $task.State, $info.LastRunTime, $info.LastTaskResult)
        }
    }
}
