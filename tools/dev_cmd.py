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


def file_hashes(root):
    import hashlib
    out = []
    for d in ("tools", "tests"):
        base = os.path.join(root, d)
        for fn in sorted(os.listdir(base)):
            if fn.endswith(".py"):
                with open(os.path.join(base, fn), "rb") as f:
                    out.append((d + "/" + fn, hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()))
    return out


def src_hash(root):
    import hashlib
    h = hashlib.sha256()
    for d in ("tools", "tests"):
        base = os.path.join(root, d)
        for fn in sorted(os.listdir(base)):
            if fn.endswith(".py"):
                h.update((d + "/" + fn).encode()); h.update(b"\0")
                with open(os.path.join(base, fn), "rb") as f:
                    h.update(f.read().replace(b"\r\n", b"\n"))      # Windows CRLF farkı parmak izini bozmasın
                h.update(b"\0")
    return h.hexdigest()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "audit"
    if cmd == "audit":
        run(["git", "branch", "--show-current"]); run(["git", "status", "--short"]); run(["git", "log", "--oneline", "-8"])
        run(["git", "rev-parse", "HEAD"]); run(["git", "remote", "-v"])
    elif cmd == "branches":
        run(["git", "branch", "-a", "--list", "*studio*"]); run(["git", "branch", "--show-current"])
    elif cmd == "newbranch":                       # çalışma ağacını bozmadan yeni dal aç (dosyalar olduğu gibi kalır)
        sys.exit(run(["git", "switch", "-c", sys.argv[2]]))
    elif cmd == "srchash":                         # kaynak parmak izi: tools/ ve tests/ içindeki .py dosyalarının sha256'sı (bulut ile PC aynı kaynağı mı test etti)
        print(src_hash(ROOT))
        if "--list" in sys.argv:                  # dosya başına sha256 (iki makinenin çıktısı diff ile karşılaştırılır)
            for pth, dg in file_hashes(ROOT):
                print(dg[:16], pth)
    elif cmd == "verify":                          # tek kaynak doğrulama: yerel HEAD, uzak dal, kirli dosya, kaynak parmak izi, zaman
        import datetime
        git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
        br = git("branch", "--show-current"); loc = git("rev-parse", "HEAD"); rem_line = git("ls-remote", "origin", "refs/heads/" + br)
        rem = rem_line.split()[0] if rem_line else ""
        dirty = git("status", "--short", "--", "tools", "tests", "series", "studio/standards")
        print("tarih=" + datetime.datetime.now().isoformat(timespec="seconds"))
        print(f"dal={br}\nyerel_HEAD={loc}\nuzak_HEAD={rem or 'YOK'}\nyerel==uzak: {loc == rem}")
        print("tools_tree@HEAD=" + git("rev-parse", "HEAD:tools") + "  tests_tree@HEAD=" + git("rev-parse", "HEAD:tests"))
        print("calisma_agaci_kaynak_sha256=" + src_hash(ROOT))
        print("kirli_dosyalar(tools,tests,series,standards): " + (dirty.replace(chr(10), " | ") or "YOK (calisma agaci == HEAD)"))
        sys.exit(0 if loc and loc == rem else 3)
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
    elif cmd == "dropbadref":                        # yalnız gösterdiği nesne YOK olan yerel dal işaretini siler (kullanıcı onayı: 27.11); sağlam dal reddedilir
        name = sys.argv[2]
        if name in ("main", "master") or "/" not in name and name == "":
            sys.exit("korumalı dal")
        ref = "refs/heads/" + name
        sha = subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        if not sha:
            sha = subprocess.run(["git", "for-each-ref", "--format=%(objectname)", ref], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        if not sha:
            sys.exit(f"{ref} bulunamadı")
        ok = subprocess.run(["git", "cat-file", "-e", sha], cwd=ROOT, capture_output=True).returncode == 0
        if ok:
            sys.exit(f"{ref} sağlam ({sha[:10]}): silinmedi")
        print(f"{ref} -> {sha[:10]} nesnesi YOK; işaret siliniyor")
        sys.exit(run(["git", "update-ref", "-d", ref]))
    elif cmd == "pull":                              # uzak dalı yalnız ileri sarma ile al (birleştirme/ezme yok); kirli dosya uzak değişiklikle çakışırsa git reddeder
        br = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        if br in ("main", "master", ""):
            sys.exit("main/master'a pull yasak")
        code = run(["git", "-c", "fetch.negotiationAlgorithm=noop", "fetch"] + (["--depth=" + sys.argv[2]] if len(sys.argv) > 2 else []) + ["origin", br])      # yerel referanslardan biri bozuksa (bad object) müzakere onu taramasın
        sys.exit(code or run(["git", "merge", "--ff-only", "origin/" + br]))
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
