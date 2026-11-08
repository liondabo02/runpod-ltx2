# Android SDK kurulumu + APK derleme (tek betik)
# 1) cmdline-tools indir  2) lisansları kabul et  3) platform+build-tools kur
# 4) local.properties yaz  5) gradlew assembleDebug
param(
    [string]$SdkRoot = 'C:\AHOS\android\sdk',
    [string]$Project = 'C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\android',
    [string]$JavaHome = 'C:\Program Files\Microsoft\jdk-17.0.20.101-hotspot'
)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

$javaExe = Join-Path $JavaHome 'bin\java.exe'
if (-not (Test-Path $javaExe)) {
    $candidate = Get-ChildItem 'C:\Program Files' -Directory -Filter 'jdk-17*' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($candidate) { $JavaHome = $candidate.FullName; $javaExe = Join-Path $JavaHome 'bin\java.exe' }
}
if (-not (Test-Path $javaExe)) { throw "JDK bulunamadi: $JavaHome" }
$env:JAVA_HOME = $JavaHome
$env:PATH = "$JavaHome\bin;" + $env:PATH
"JAVA_HOME=$JavaHome"
& $javaExe -version 2>&1 | Select-Object -First 1

$toolsDir = Join-Path $SdkRoot 'cmdline-tools'
$latest = Join-Path $toolsDir 'latest'
if (-not (Test-Path (Join-Path $latest 'bin\sdkmanager.bat'))) {
    New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
    $zip = Join-Path $env:TEMP 'cmdline-tools.zip'
    if (-not (Test-Path $zip)) {
        "indiriliyor: cmdline-tools"
        & curl.exe -L --fail --max-time 3600 -o $zip 'https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip'
        if ($LASTEXITCODE -ne 0) { throw "cmdline-tools indirilemedi" }
    }
    $extract = Join-Path $env:TEMP 'cmdline-unzip'
    if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }
    Expand-Archive -Path $zip -DestinationPath $extract -Force
    New-Item -ItemType Directory -Force -Path $latest | Out-Null
    Copy-Item (Join-Path $extract 'cmdline-tools\*') $latest -Recurse -Force
}
"sdkmanager: " + (Test-Path (Join-Path $latest 'bin\sdkmanager.bat'))

$sdkmanager = Join-Path $latest 'bin\sdkmanager.bat'
$env:ANDROID_HOME = $SdkRoot
$env:ANDROID_SDK_ROOT = $SdkRoot

"lisanslar kabul ediliyor"
$yes = ("y`n" * 40)
$yes | & $sdkmanager --sdk_root=$SdkRoot --licenses 2>&1 | Select-Object -Last 3

"paketler kuruluyor (platform-tools, android-34, build-tools 34.0.0)"
& $sdkmanager --sdk_root=$SdkRoot 'platform-tools' 'platforms;android-34' 'build-tools;34.0.0' 2>&1 | Select-Object -Last 5

if (-not (Test-Path (Join-Path $SdkRoot 'platforms\android-34'))) { throw "android-34 platformu kurulamadi" }

"local.properties yaziliyor"
$escaped = $SdkRoot.Replace('\', '\\')
Set-Content -Path (Join-Path $Project 'local.properties') -Value "sdk.dir=$escaped" -Encoding ascii

"gradle derlemesi basliyor"
Push-Location $Project
try {
    & cmd /c "gradlew.bat --no-daemon assembleDebug" 2>&1 | Select-Object -Last 20
    "gradle exit=$LASTEXITCODE"
} finally {
    Pop-Location
}

$apk = Get-ChildItem (Join-Path $Project 'app\build\outputs\apk\debug') -Filter '*.apk' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($apk) {
    "APK HAZIR: " + $apk.FullName + " (" + [math]::Round($apk.Length / 1MB, 1) + " MB)"
} else {
    "APK URETILEMEDI"
}
