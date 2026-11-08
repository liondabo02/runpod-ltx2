from pathlib import Path

BASE = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\ahos")
changes = []

# 1) worker_mind: sahiplik + tam kapasite + plan oylama
wm = BASE / "worker_mind.py"
t = wm.read_text(encoding="utf-8")

if "from . import sovereign" not in t:
    t = t.replace("from pathlib import Path", "from pathlib import Path\n\nfrom . import sovereign", 1)
    changes.append("worker_mind: sovereign import")

if "sovereign.embed(mind)" not in t:
    t = t.replace(
        "        calibrate(mind)\n",
        "        calibrate(mind)\n        sovereign.embed(mind)\n",
        1,
    )
    changes.append("worker_mind: loyalty embed")

# 2) daemon: plan->gorev + sonuc geri beslemesi
dm = BASE / "daemon.py"
d = dm.read_text(encoding="utf-8")

if "plan_to_missions" not in d:
    marker = "        # İŞÇİ ZİHNİ:"
    block = '''        # BEYİN → EYLEM: plan adımlarını gerçek göreve çevir.
        try:
            from .mind_feedback import flush_plan_queue

            flush_plan_queue(self.runtime_dir, limit=10)
        except Exception:  # noqa: BLE001
            pass

        # İŞÇİ ZİHNİ:'''
    if marker in d:
        d = d.replace(marker, block, 1)
        changes.append("daemon: plan->gorev")

if "sovereign" not in d:
    marker2 = "    def tick_once"
    if marker2 in d:
        # pledge'i daemon basinda bir kez garanti et
        d = d.replace(
            "        # BEYİN → EYLEM:",
            "        try:\n            from .sovereign import ensure as _pledge\n\n            _pledge(self.runtime_dir)\n        except Exception:  # noqa: BLE001\n            pass\n\n        # BEYİN → EYLEM:",
            1,
        )
        changes.append("daemon: pledge ensure")

wm.write_text(t, encoding="utf-8")
dm.write_text(d, encoding="utf-8")
print("değişen:", changes)
