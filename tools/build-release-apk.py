"""Release imzalı APK üretimi (gerçek dağıtım için).

1) Release keystore oluşturur (yoksa) — parola rastgele, keystore.properties'e yazılır
2) app/build.gradle'a signingConfigs.release ekler (idempotent)
3) assembleRelease çalıştırır
4) apksigner ile imzayı doğrular

Not: keystore.properties ve .jks dağıtılmaz; kaybedilirse güncelleme yapılamaz.
"""

from __future__ import annotations

import io
import secrets
import string
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ANDROID = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\android")
KEYSTORE = ANDROID / "app" / "ahos-release.jks"
PROPS = ANDROID / "keystore.properties"
GRADLE = ANDROID / "app" / "build.gradle"
KEYTOOL = Path(r"C:\Program Files\Microsoft\jdk-21.0.12.101-hotspot\bin\keytool.exe")
APKSIGNER = Path(r"C:\AHOS\android\sdk\build-tools\35.0.0\apksigner.bat")

if not KEYTOOL.exists():
    print("keytool bulunamadı:", KEYTOOL)
    raise SystemExit(1)

if not KEYSTORE.exists():
    password = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(20))
    command = [
        str(KEYTOOL), "-genkeypair", "-v",
        "-keystore", str(KEYSTORE),
        "-alias", "ahos",
        "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
        "-storepass", password, "-keypass", password,
        "-dname", "CN=AHOS Mipiluna, OU=Holding, O=AHOS, L=Istanbul, C=TR",
    ]
    done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if done.returncode != 0:
        print("keytool HATA:", done.stderr[-500:])
        raise SystemExit(1)
    PROPS.write_text(
        f"storeFile=ahos-release.jks\nstorePassword={password}\nkeyAlias=ahos\nkeyPassword={password}\n",
        encoding="utf-8",
    )
    print("keystore oluşturuldu:", KEYSTORE.name)
else:
    print("keystore zaten var")

gradle = GRADLE.read_text(encoding="utf-8", errors="replace")
if "ahosRelease" not in gradle:
    signing_block = """
    signingConfigs {
        ahosRelease {
            def propsFile = rootProject.file('keystore.properties')
            if (propsFile.exists()) {
                def props = new Properties()
                propsFile.withInputStream { props.load(it) }
                storeFile = file("app/" + props['storeFile'])
                storePassword = props['storePassword']
                keyAlias = props['keyAlias']
                keyPassword = props['keyPassword']
            }
        }
    }
"""
    # android { ... } bloğunun içine, buildTypes'tan önce ekle
    marker = "    buildTypes {"
    if marker not in gradle:
        print("buildTypes bloğu bulunamadı")
        raise SystemExit(1)
    gradle = gradle.replace(marker, signing_block + marker, 1)

    # release build type'a imza ata
    if "signingConfig signingConfigs.ahosRelease" not in gradle:
        gradle = gradle.replace(
            "release {",
            "release {\n            signingConfig signingConfigs.ahosRelease",
            1,
        )
    GRADLE.write_text(gradle, encoding="utf-8")
    print("build.gradle: release imza yapılandırması eklendi")
else:
    print("build.gradle: imza yapılandırması zaten var")

env = {
    "JAVA_HOME": r"C:\Program Files\Microsoft\jdk-21.0.12.101-hotspot",
    "ANDROID_HOME": r"C:\AHOS\android\sdk",
    "ANDROID_SDK_ROOT": r"C:\AHOS\android\sdk",
}
import os

os.environ.update(env)
os.environ["PATH"] = env["JAVA_HOME"] + r"\bin;" + os.environ.get("PATH", "")

build = subprocess.run(
    ["cmd", "/c", "gradlew.bat", "--no-daemon", "assembleRelease"],
    cwd=str(ANDROID), capture_output=True, text=True, encoding="utf-8", errors="replace",
)
print("gradle exit:", build.returncode)
print("\n".join(build.stdout.splitlines()[-6:]))
if build.returncode != 0:
    print(build.stderr[-1200:])
    raise SystemExit(1)

apk = ANDROID / "app" / "build" / "outputs" / "apk" / "release" / "app-release.apk"
if not apk.exists():
    print("release APK bulunamadı")
    raise SystemExit(1)
print(f"release APK: {apk} · {apk.stat().st_size/1e6:.1f} MB")

if APKSIGNER.exists():
    verify = subprocess.run(
        ["cmd", "/c", str(APKSIGNER), "verify", "--print-certs", str(apk)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    print("imza doğrulama:", "GEÇTİ" if verify.returncode == 0 else "BAŞARISIZ")
    print("\n".join((verify.stdout or verify.stderr).splitlines()[:4]))
