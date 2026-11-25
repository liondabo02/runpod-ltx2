"""Güvenli geliştirici komutları (yalnız izin listesindeki git/pytest işlemleri). Yasak: force push, reset --hard, clean, rm.
Kullanım: dev_cmd.py audit | test | commit "<mesaj>" <dosya...> | push | sha (yerel HEAD = uzak dal mı)"""
import os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, "ahos_core")


def run(args, cwd=ROOT, timeout=1700):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    print("$", " ".join(args), "-> exit", r.returncode)
    print((r.stdout or "")[-4000:], (r.stderr or "")[-1500:])
    return r.returncode


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "audit"
    if cmd == "audit":
        run(["git", "branch", "--show-current"]); run(["git", "status", "--short"]); run(["git", "log", "--oneline", "-8"])
        run(["git", "rev-parse", "HEAD"]); run(["git", "remote", "-v"])
    elif cmd == "branches":
        run(["git", "branch", "-a", "--list", "*studio*"]); run(["git", "branch", "--show-current"])
    elif cmd == "newbranch":                       # çalışma ağacını bozmadan yeni dal aç (dosyalar olduğu gibi kalır)
        sys.exit(run(["git", "switch", "-c", sys.argv[2]]))
    elif cmd == "sha":
        run(["git", "rev-parse", "HEAD"]); run(["git", "fetch", "--dry-run"]); run(["git", "status", "-sb"])
    elif cmd == "test":
        sys.exit(run([sys.executable, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider"] + sys.argv[2:], cwd=CORE))
    elif cmd == "commit":
        msg, files = sys.argv[2], sys.argv[3:]
        if not files or any(f.startswith("-") or ".." in f for f in files):
            sys.exit("dosya listesi gerekli (yalnız açık dosya adları)")
        run(["git", "add", "--"] + files)
        sys.exit(run(["git", "commit", "-m", msg]))
    elif cmd == "push":
        br = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        if br in ("main", "master", ""):
            sys.exit("main/master'a push yasak")
        sys.exit(run(["git", "push", "origin", br]))                # normal push; force yok
    elif cmd == "sha":      # yerel HEAD ile uzak dal SHA'sı aynı mı (push doğrulaması)
        br = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        loc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        r = subprocess.run(["git", "ls-remote", "origin", "refs/heads/" + br], cwd=ROOT, capture_output=True, text=True)
        rem = r.stdout.split()[0] if r.stdout.strip() else ""
        print(f"dal={br} yerel={loc} uzak={rem or 'YOK'} -> {'ESLESTI' if loc and loc == rem else 'ESLESMEDI'}")
        sys.exit(0 if loc and loc == rem else 3)
    else:
        sys.exit("bilinmeyen komut")


if __name__ == "__main__":
    main()
