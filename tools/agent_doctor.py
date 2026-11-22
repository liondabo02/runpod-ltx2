#!/usr/bin/env python3
"""Ajanları düzelten ajan: her işçi modülünü import/test eder, bozukları gözlem + öneri olarak yazar.
Kodu kendisi DEĞİŞTİRMEZ (sandbox -> test -> sahip onayı)."""
import importlib, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
MODULES = ["showrunner", "writers_room", "voice_worker", "localisation_worker", "animatic_worker", "character_worker",
           "render_worker", "video_qa", "music_worker", "support_workers", "task_observer", "lessons"]


def check_imports():
    bad = {}
    for m in MODULES:
        try:
            importlib.import_module(m)
        except Exception as e:  # noqa: BLE001
            bad[m] = "%s: %s" % (type(e).__name__, e)
    return bad


def check_tests():
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", os.path.join(ROOT, "tests")],
                       capture_output=True, text=True, cwd=ROOT)
    return r.returncode == 0, (r.stderr or r.stdout)[-600:]


def main():
    import task_observer as to
    bad = check_imports(); ok, tail = check_tests()
    for m, e in bad.items():
        to.log(m, "friction", "modül yüklenemedi: " + e[:120], "import hatasını gider")
    if not ok:
        to.log("tests", "friction", "birim testleri başarısız: " + tail[-120:], "başarısız testi incele")
    rep = {"status": "PASSED" if not bad and ok else "FAILED", "import_errors": bad, "tests_ok": ok}
    os.makedirs(os.path.join(ROOT, "studio", "reports"), exist_ok=True)
    json.dump(rep, open(os.path.join(ROOT, "studio", "reports", "agent_doctor.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False, indent=1)); return 0 if rep["status"] == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
