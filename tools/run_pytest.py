"""PC'de odaklı pytest çalıştırıcı (kuyruk işi). Çıktıyı qa/pytest_pc.txt'ye yazar; çıkış kodu pytest'inkidir."""
import subprocess, sys, os, time, platform
root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
paths = sys.argv[1:] or ["tests"]
t0 = time.time()
r = subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"] + paths, cwd=root, capture_output=True, text=True)
os.makedirs(os.path.join(root, "qa"), exist_ok=True)
head = f"# pytest PC | {platform.platform()} | python {platform.python_version()} | {time.strftime('%Y-%m-%d %H:%M:%S')} | {round(time.time()-t0,1)} sn | kod {r.returncode}\n"
open(os.path.join(root, "qa", "pytest_pc.txt"), "w", encoding="utf-8").write(head + r.stdout[-6000:] + r.stderr[-1500:])
print(head + r.stdout[-1500:]); sys.exit(r.returncode)
