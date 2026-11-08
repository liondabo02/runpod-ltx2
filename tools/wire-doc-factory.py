from pathlib import Path

p = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\ahos\owner_console.py")
t = p.read_text(encoding="utf-8")

needle = "                if load_settings() is not None:"
replacement = (
    "                # Önce model bağımsız belge fabrikası: gerçek veriden üretir.\n"
    "                try:\n"
    "                    from .doc_factory import make_document_factory_executor\n"
    "\n"
    "                    return make_document_factory_executor(self.runtime_dir)\n"
    "                except Exception:  # noqa: BLE001 - geri dönüş korunur\n"
    "                    pass\n"
    "                if load_settings() is not None:"
)

if "doc_factory" in t:
    print("zaten bağlı")
elif needle in t:
    t = t.replace(needle, replacement, 1)
    p.write_text(t, encoding="utf-8")
    print("belge fabrikası bağlandı")
else:
    print("desen bulunamadı")
