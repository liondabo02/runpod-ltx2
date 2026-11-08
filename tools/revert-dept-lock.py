from pathlib import Path

p = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\ahos\owner_console.py")
t = p.read_text(encoding="utf-8")
start = t.find("    def create_department(self, *args, **kwargs):")
if start == -1:
    print("kilit bloğu bulunamadı")
else:
    end = t.find('raise RuntimeError("yeni departman kurma kapalı")', start)
    end = t.find("\n", end) + 1
    t = t[:start] + t[end:]
    p.write_text(t, encoding="utf-8")
    print("kilit bloğu geri alındı")
