import os
import subprocess
import time
import urllib.request

PY = r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\control_plane_v2\.venv\Scripts\python.exe"
CWD = r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core"

env = dict(os.environ)
env["PYTHONPATH"] = CWD
proc = subprocess.Popen(
    [PY, "-m", "ahos.office_server", "--runtime-dir", "runtime", "--port", "8799"],
    cwd=CWD, env=env, creationflags=0x00000008 | 0x00000200,
    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
print("ofis pid:", proc.pid)
for _ in range(10):
    time.sleep(2)
    try:
        with urllib.request.urlopen("http://127.0.0.1:8799/ofis", timeout=5) as resp:
            html = resp.read().decode()
        print("/ofis:", len(html), "bayt")
        print("bina:", "CEO Ofisi" in html, "| ortak alan:", "Ortak Alan" in html,
              "| tema:", "THEMES" in html, "| kapı:", "phase === 'door'" in html)
        break
    except Exception as exc:
        print("  deneme:", type(exc).__name__)
