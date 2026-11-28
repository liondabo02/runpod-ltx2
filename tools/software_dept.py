#!/usr/bin/env python3
"""Yazılım Şirketi: stüdyonun motor geliştirme departmanının gerçek araçları.

Komutlar:
  durum                     Motor yetenek envanteri özeti + öncelikli eksikler (tools/engine_gaps.py)
  kabul --test T [--test T2] [--base REF] [--kirmizi-gerekmez GEREKCE]
                            Kırmızı-yeşil kabul kapısı: verilen testler YENİ kodda geçmeli ve ESKİ kodda
                            (REF, varsayılan HEAD~1; geçici git worktree) düşmeli. Eski kodda da geçen test
                            hiçbir şeyi kanıtlamaz -> RED. Sonuç runtime/software-dept/kabul.jsonl'e yazılır.
  ofis-senkron [--son N]    Daldaki gerçek commit'leri 'software' işçisinin bitmiş işi olarak ofis olay
                            kaydına (worker_events biçimi) işler. Aynı commit iki kez yazılmaz.

Kurallar (skills/software/SKILL.md): ücretli çağrı yok, force push yok, main'e merge yok, sahte PASS yok.
Bu araç kod YAZMAZ; geliştirmeyi yapan oturum (bulut turu ya da PC oturumu) bu kapılardan geçmek zorundadır.
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import engine_gaps  # noqa: E402

WORKER = "software"
STATE_DIR = os.path.join("runtime", "software-dept")
CODE_RE = re.compile(r"^([A-Z]{1,3}\d+[a-z]?(?:-\d+)?)\b")


def _run(cmd, cwd, timeout=None):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        return 124, "ZAMAN_ASIMI: %s" % e
    except OSError as e:
        return 127, "CALISTIRILAMADI: %s" % e


def _git(root, *args, run=_run):
    return run(["git"] + list(args), root)


def _tail(text, n=6):
    lines = [l for l in (text or "").strip().splitlines() if l.strip()]
    return lines[-n:]


def _append(root, name, row):
    d = os.path.join(root, STATE_DIR)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name), "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def pytest_cmd(tests):
    return [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"] + list(tests)


def acceptance(root, tests, base="HEAD~1", no_red_reason=None, run=_run, keep_record=True):
    """Kırmızı-yeşil kabul. Döner: {"sonuc": KABUL|KABUL_KIRMIZISIZ|RED, "neden", ...kanıt}."""
    tests = [t for t in tests if t]
    if not tests:
        raise ValueError("en az bir --test gerekli")
    rc, head = _git(root, "rev-parse", "HEAD", run=run)
    head = head.strip() if rc == 0 else "?"
    out = {"at": round(time.time(), 1), "head": head, "base": base, "testler": tests}
    g_rc, g_out = run(pytest_cmd(tests), root)
    out["yeni_kod"] = {"exit": g_rc, "son": _tail(g_out)}
    if g_rc != 0:
        out.update(sonuc="RED", neden="YENI_KODDA_DUSUYOR")
    elif no_red_reason:
        out.update(sonuc="KABUL_KIRMIZISIZ", neden="kırmızı adım atlandı: " + no_red_reason)
    else:
        tmp = tempfile.mkdtemp(prefix="ahos-kabul-")
        wt = os.path.join(tmp, "eski")
        try:
            w_rc, w_out = _git(root, "worktree", "add", "--detach", wt, base, run=run)
            if w_rc != 0:
                out.update(sonuc="RED", neden="ESKI_KOD_HAZIRLANAMADI", eski_kod={"exit": w_rc, "son": _tail(w_out)})
            else:
                rc2, b = _git(root, "rev-parse", base, run=run)
                out["base_sha"] = b.strip() if rc2 == 0 else "?"
                for t in tests:  # yeni testler eski kodun üstünde koşar
                    rel = t.split("::")[0]
                    src = os.path.join(root, rel)
                    if os.path.isfile(src):
                        os.makedirs(os.path.dirname(os.path.join(wt, rel)), exist_ok=True)
                        shutil.copy2(src, os.path.join(wt, rel))
                r_rc, r_out = run(pytest_cmd(tests), wt)
                out["eski_kod"] = {"exit": r_rc, "son": _tail(r_out)}
                if r_rc == 0:
                    out.update(sonuc="RED", neden="TEST_ESKI_KODDA_DA_GECIYOR (kusuru yakalamıyor)")
                elif r_rc in (124, 127):
                    out.update(sonuc="RED", neden="ESKI_KODDA_TEST_KOSAMADI")
                else:
                    out.update(sonuc="KABUL", neden="yeni kodda geçti, eski kodda düştü")
        finally:
            _git(root, "worktree", "remove", "--force", wt, run=run)
            shutil.rmtree(tmp, ignore_errors=True)
    if keep_record:
        _append(root, "kabul.jsonl", out)
    return out


def _events_path(root):
    return os.environ.get("AHOS_EVENTS_PATH") or os.path.join(root, "studio", "queue", "events.jsonl")


def _known_jobs(path):
    jobs = set()
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("worker") == WORKER:
                    jobs.add(row.get("job"))
    except OSError:
        pass
    return jobs


def office_sync(root, last=30, run=_run, events_path=None):
    """Daldaki son commit'leri ofis olay kaydına 'software' işçisinin bitmiş işi olarak ekler. Eklenen sayısını döner."""
    rc, log = _git(root, "log", "-n", str(int(last)), "--format=%H%x1f%ct%x1f%s", run=run)
    if rc != 0:
        raise RuntimeError("git log çalışmadı: " + " ".join(_tail(log, 2)))
    path = events_path or _events_path(root)
    known = _known_jobs(path)
    rows = []
    for line in reversed([l for l in log.splitlines() if l.strip()]):
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        sha, ct, subj = parts
        job = "git-" + sha[:12]
        if job in known:
            continue
        m = CODE_RE.match(subj)
        text = ("%s: %s" % (m.group(1), subj[len(m.group(0)):].strip())) if m else subj.strip()
        rows.append({"at": float(ct), "job": job, "worker": WORKER, "kind": "done",
                     "text": ("motor geliştirmesi tamam (%s) — %s" % (sha[:7], text))[:300]})
    if rows:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def status(root):
    rep = engine_gaps.check(root)
    by = {r["id"]: r for r in rep["yetenekler"]}
    lines = ["Yazılım Şirketi durum", "yetenek %d: " % rep["yetenek_sayisi"] +
             ", ".join("%s %d" % (k, rep["toplam"][k]) for k in engine_gaps.ORDER),
             "sorunlu skill: %d/%d" % (sum(1 for s in rep["skilller"] if s["sorunlar"]), len(rep["skilller"])),
             "öncelikli eksikler:"]
    for i in rep["eksikler"][:8]:
        r = by[i]
        lines.append("  %s [%s] %s (%s)" % (i, r["durum"], r["yetenek"], r["isci"]))
    return "\n".join(lines), rep


def main(argv=None):
    ap = argparse.ArgumentParser(description="Yazılım Şirketi araçları")
    ap.add_argument("--root", default=ROOT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("durum")
    k = sub.add_parser("kabul")
    k.add_argument("--test", action="append", required=True)
    k.add_argument("--base", default="HEAD~1")
    k.add_argument("--kirmizi-gerekmez", dest="no_red")
    o = sub.add_parser("ofis-senkron")
    o.add_argument("--son", type=int, default=30)
    a = ap.parse_args(argv)
    if a.cmd == "durum":
        print(status(a.root)[0]); return 0
    if a.cmd == "kabul":
        r = acceptance(a.root, a.test, a.base, a.no_red)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["sonuc"].startswith("KABUL") else 1
    if a.cmd == "ofis-senkron":
        print("ofise eklenen iş:", office_sync(a.root, a.son)); return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
