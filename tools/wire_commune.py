from pathlib import Path

p = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\ahos\daemon.py")
t = p.read_text(encoding="utf-8")

if "from .commune import converse" in t:
    print("zaten bağlı")
else:
    marker = "        # BEYİN → EYLEM:"
    block = (
        "        # KONUŞMA: işçiler birbirine soru sorar, cevap verir.\n"
        "        try:\n"
        "            import json as _json4\n"
        "\n"
        "            from .commune import converse as _converse\n"
        "\n"
        '            _book4 = _json4.loads((self.runtime_dir / "departments.json").read_text(encoding="utf-8"))\n'
        '            _deps4 = _book4.get("departments") if isinstance(_book4, dict) else _book4\n'
        "            _talk = _converse(self.runtime_dir, _deps4 or [], rounds=2)\n"
        "            self.state.infra = self.state.infra or {}\n"
        '            self.state.infra["commune"] = _talk\n'
        "        except Exception:  # noqa: BLE001\n"
        "            pass\n"
        "\n"
        + marker
    )
    if marker not in t:
        print("işaret bulunamadı")
    else:
        t = t.replace(marker, block, 1)
        p.write_text(t, encoding="utf-8")
        print("daemon: konuşma bağlandı")
