"""Ofisi (8799) ve çizgi film panelini başlatır. Ofis verisi (81 işçi, 17 departman) eski runtime klasöründen okunur."""
import os, socket, subprocess, sys, time, webbrowser

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD = r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2"
RUNTIME = os.path.join(OLD, "ahos_core", "runtime")
VENV_PY = os.path.join(OLD, "control_plane_v2", ".venv", "Scripts", "python.exe")
PY = VENV_PY if os.path.exists(VENV_PY) else sys.executable
FLAGS = 0x00000008 | 0x00000200 if os.name == "nt" else 0


def busy(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    if not os.path.isdir(RUNTIME):
        print("UYARI: eski runtime bulunamadı:", RUNTIME, "- boş ofis açılacak")
        RUNTIME_USE = os.path.join(REPO, "ahos_core", "runtime")
    else:
        RUNTIME_USE = RUNTIME
    env = dict(os.environ, PYTHONPATH=os.path.join(REPO, "ahos_core"), AHOS_STUDIO_PYTHON=sys.executable)
    quiet = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=FLAGS)
    if not busy(8787):
        subprocess.Popen([sys.executable, os.path.join(REPO, "tools", "office_server.py")], cwd=REPO, **quiet)
    if busy(8799):
        print("8799 zaten dolu: ofis eski kodla çalışıyor olabilir. Önce kapat:")
        print("  Get-NetTCPConnection -LocalPort 8799 -State Listen | % { Stop-Process -Id $_.OwningProcess -Force }")
    else:
        subprocess.Popen([PY, "-m", "ahos.office_server", "--runtime-dir", RUNTIME_USE, "--port", "8799"],
                         cwd=os.path.join(REPO, "ahos_core"), env=env, **quiet)
        print("Ofis başlatılıyor, runtime:", RUNTIME_USE)
    time.sleep(3)
    webbrowser.open("http://127.0.0.1:8799/ofis3d")


if __name__ == "__main__":
    main()
