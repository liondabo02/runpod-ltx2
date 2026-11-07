"""V5 GÖREV 013/018/019/020 — canlı işçi katmanı kabul kontrolü (salt okunur).

Çalışan kontrol paneline HTTP ile bağlanır; hiçbir veri yazmaz. Her kontrol
gerçek yanıt üzerinden yapılır ve sonuç JSON olarak basılır.

Kullanım:
    python tools/worker_layer_check.py
    python tools/worker_layer_check.py --base http://127.0.0.1:8766
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STATES = {"working", "researching", "learning", "reviewing", "collaborating",
          "waiting_dependency", "waiting_approval", "blocked", "idle", "offline"}


def get(base: str, path: str, timeout: float = 20.0) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(base + path, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8766")
    args = parser.parse_args(argv)
    base = args.base.rstrip("/")
    checks: list[dict] = []

    def check(name: str, ok: bool, detail) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    status, body = get(base, "/api/roster")
    roster = json.loads(body) if status == 200 else {}
    check("roster 200", status == 200, status)
    check("roster 81 işçi", len(roster) == 81, len(roster))
    check("roster alanları", all(isinstance(row, dict) and row.get("name")
                                 for row in roster.values()), len(roster))

    status, body = get(base, "/api/agent-office")
    office = json.loads(body) if status == 200 else {}
    totals = (office or {}).get("totals") or {}
    states = totals.get("states") or {}
    check("agent-office 200", status == 200, status)
    check("durum kodları geçerli", set(states) == STATES, sorted(states))
    check("durum toplamı = işçi", sum(states.values()) == totals.get("workers"),
          {"sum": sum(states.values()), "workers": totals.get("workers")})
    check("bilinmeyen işçi 47", totals.get("unknown_workers") == 47,
          totals.get("unknown_workers"))

    workers = [worker for dep in (office or {}).get("departments") or []
               for worker in dep.get("workers") or []]
    sample = next((worker for worker in workers if worker.get("runs")), None) or {}
    if sample:
        status, body = get(base, "/api/worker-card/" + sample["worker_id"])
        card = json.loads(body) if status == 200 else {}
        check("kart 200", status == 200, status)
        check("kart durumu geçerli", (card.get("state") or {}).get("code") in STATES,
              (card.get("state") or {}).get("code"))
        check("özel hafıza gizli", card.get("private_memory_hidden") is True
              and "private" not in card, card.get("private_memory_hidden"))
        page_status, page = get(base, "/worker/" + sample["worker_id"])
        check("kart sayfası 200", page_status == 200, page_status)
        check("kart sayfası ismi taşır", str(sample.get("name"))[:20] in page, len(page))

    status, _ = get(base, "/api/worker-card/olmayan-isci")
    check("olmayan işçi 404", status == 404, status)
    status, _ = get(base, "/worker/olmayan-isci")
    check("olmayan kart 404", status == 404, status)

    status, panel = get(base, "/intelligence")
    check("panel 200", status == 200, status)
    check("panel durum sütunu", "<th>Durum</th>" in panel, None)
    links = len(re.findall(r'href="/worker/', panel))
    check("panel işçi kartı linkleri", links == len(roster), {"links": links,
                                                              "roster": len(roster)})
    check("panel bayat/kayıt yok işareti", "kayıt yok" in panel and "eski" in panel, None)

    failed = [row for row in checks if not row["ok"]]
    print(json.dumps({"base": base, "checks": checks, "passed": len(checks) - len(failed),
                      "failed": len(failed)}, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
