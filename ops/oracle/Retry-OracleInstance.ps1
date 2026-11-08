#requires -Version 5.1
<#
.SYNOPSIS
  Oracle'da "Out of capacity" bitene kadar otomatik örnek oluşturma denemesi.

.DESCRIPTION
  OCI CLI ile, verilen availability domain'leri sırayla dener; kapasite hatasında
  bekleyip tekrar dener. Başarılı olunca örneğin public IP'sini yazar.

  Ön koşul: `oci` CLI kurulu ve `~/.oci/config` yapılandırılmış olmalı
  (Oracle konsolu → Profil → API keys → Add API key → config dosyasını indir).

.EXAMPLE
  .\Retry-OracleInstance.ps1 `
      -CompartmentId ocid1.compartment.oc1..xxxx `
      -SubnetId ocid1.subnet.oc1..xxxx `
      -SshPublicKeyFile "$env:USERPROFILE\.ssh\ahos-quality-99.pub"
#>
param(
    [Parameter(Mandatory = $true)][string]$CompartmentId,
    [Parameter(Mandatory = $true)][string]$SubnetId,
    [string]$SshPublicKeyFile = "$env:USERPROFILE\.ssh\ahos-quality-99.pub",
    [string]$UserDataFile = (Join-Path $PSScriptRoot 'cloud-init-ollama.yaml'),
    [string[]]$AvailabilityDomains = @(),
    [string]$Shape = 'VM.Standard.A1.Flex',
    [int]$Ocpus = 2,
    [int]$MemoryGB = 12,
    [int]$IntervalSeconds = 120,
    [double]$MaxHours = 6,
    [string]$DisplayName = 'AHOS-QUALITY-99'
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Command oci -ErrorAction SilentlyContinue)) {
    throw "OCI CLI bulunamadı. Kurulum: https://docs.oracle.com/iaas/Content/API/SDKDocs/cliinstall.htm"
}
if (-not (Test-Path -LiteralPath $SshPublicKeyFile)) {
    throw "SSH public key yok: $SshPublicKeyFile  (ssh-keygen -t ed25519 -f ... ile üretin)"
}

function Get-AvailabilityDomains {
    if ($AvailabilityDomains.Count -gt 0) { return $AvailabilityDomains }
    $ads = oci iam availability-domain list --compartment-id $CompartmentId --query 'data[].name' --raw-output | ConvertFrom-Json
    return @($ads)
}

function Get-UbuntuImageId {
    param([string]$Ad)
    $id = oci compute image list `
        --compartment-id $CompartmentId `
        --operating-system 'Canonical Ubuntu' `
        --operating-system-version '24.04' `
        --shape $Shape `
        --sort-by TIMECREATED --sort-order DESC `
        --query 'data[0].id' --raw-output
    if (-not $id) {
        throw "Ubuntu 24.04 imajı bulunamadı; --image-id parametresiyle elle verin."
    }
    return $id
}

$sshKey = Get-Content -LiteralPath $SshPublicKeyFile -Raw
$userData = ''
if (Test-Path -LiteralPath $UserDataFile) {
    $bytes = [System.IO.File]::ReadAllBytes((Resolve-Path $UserDataFile))
    $userData = [Convert]::ToBase64String($bytes)
}

$ads = @(Get-AvailabilityDomains)
$imageId = Get-UbuntuImageId -Ad $ads[0]
$deadline = (Get-Date).AddHours($MaxHours)
$attempt = 0
$stateFile = Join-Path $PSScriptRoot 'last-instance.json'

while ((Get-Date) -lt $deadline) {
    foreach ($ad in $ads) {
        $attempt++
        $metadata = @{ ssh_authorized_keys = $sshKey }
        if ($userData) { $metadata['user_data'] = $userData }
        $metadataJson = $metadata | ConvertTo-Json -Compress
        $shapeConfig = @{ ocpus = $Ocpus; memoryInGBs = $MemoryGB } | ConvertTo-Json -Compress

        Write-Host ("[{0}] deneme {1}: {2} / {3} OCPU {4} GB" -f (Get-Date -Format 'HH:mm:ss'), $attempt, $ad, $Shape, $Ocpus)
        $output = & oci compute instance launch `
            --availability-domain $ad `
            --compartment-id $CompartmentId `
            --shape $Shape `
            --shape-config $shapeConfig `
            --image-id $imageId `
            --subnet-id $SubnetId `
            --assign-public-ip true `
            --display-name $DisplayName `
            --metadata $metadataJson 2>&1
        $exit = $LASTEXITCODE
        $text = ($output | Out-String)

        if ($exit -eq 0) {
            $instanceId = ($text | ConvertFrom-Json).'data'.id
            Write-Host "OLUŞTURULDU: $instanceId"
            Start-Sleep -Seconds 20
            $publicIp = oci compute instance list-vnics --instance-id $instanceId --query 'data[0]."public-ip"' --raw-output
            $record = @{ instance_id = $instanceId; public_ip = $publicIp; availability_domain = $ad; at = (Get-Date).ToUniversalTime().ToString('o') }
            $record | ConvertTo-Json | Set-Content -Path $stateFile -Encoding utf8
            Write-Host "PUBLIC IP: $publicIp"
            Write-Host "Sonraki adım: .\Connect-AhosModel.ps1 -VmIp $publicIp"
            exit 0
        }

        if ($text -match 'Out of capacity|OutOfCapacity|capacity') {
            Write-Host "  kapasite yok; sonraki deneme $(($IntervalSeconds)) sn sonra"
        } else {
            Write-Host ("  hata: " + ($text.Trim().Split("`n")[-1]))
        }
    }
    Start-Sleep -Seconds $IntervalSeconds
}

Write-Warning "Süre doldu, örnek oluşturulamadı. Farklı bölge veya 1 OCPU / 6 GB deneyin."
exit 1
