"""Q6: ofis sunucusu, çıktısı dar bir kod sayfasına yönlendirilince başlangıç mesajında çökmez ve gerçekten hizmet verir."""
import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(ROOT, "tools", "office_server.py")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.parametrize("encoding", ["cp1252", "cp1254", "cp857", "ascii"])
def test_server_starts_and_serves_with_redirected_narrow_console(tmp_path, encoding):
    port = free_port()
    log = tmp_path / "ofis.log"
    env = dict(os.environ, PYTHONIOENCODING=encoding, PYTHONUTF8="0", AHOS_OFFICE_PORT=str(port))
    with open(log, "wb") as out:
        proc = subprocess.Popen([sys.executable, SERVER], stdout=out, stderr=subprocess.STDOUT, env=env)
        try:
            status = None
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(100):
                if proc.poll() is not None:
                    break
                try:
                    status = opener.open(f"http://127.0.0.1:{port}/insan", timeout=2).status
                    break
                except OSError:
                    time.sleep(0.1)
            assert status == 200 and proc.poll() is None, log.read_bytes()[-800:]
        finally:
            proc.terminate()
            proc.wait(timeout=10)
    text = log.read_bytes()
    assert str(port).encode() in text and b"Traceback" not in text, text
