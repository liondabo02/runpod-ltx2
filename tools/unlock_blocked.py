"""Bayat kilitli engelli gorevleri temizleyip yeniden kuyruga alir."""
import json, sqlite3, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
RUNTIME = CORE / "runtime"
sys.path.insert(0, str(CORE))


def main(limit: int = 40) -> int:
    tb = RUNTIME / "taskboard.json"
    con = sqlite3.connect(RUNTIME / "company-service.db", timeout=30)
    blocked = [r[0] for r in con.execute("select mission_id from missions where status='blocked'").fetchall()]
    cleared = 0
    if tb.exists():
        try:
            data = json.loads(tb.read_text(encoding="utf-8"))
            locks = data.get("locks") or data
            if isinstance(locks, dict):
                for mid in list(locks.keys()):
                    if mid in set(blocked):
                        locks.pop(mid, None)
                        cleared += 1
                tb.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
    n = con.execute(
        "update missions set status='pending', attempts=0, max_attempts=2, next_attempt_at=0, "
        "lease_owner=NULL, lease_until=NULL, last_error='yeniden: kilit temizlendi' "
        "where status='blocked'"
    ).rowcount
    con.commit()
    print(f"kilit temizlenen: {cleared} | yeniden kuyruga: {n}")

    from ahos.owner_console import build_default_console
    from ahos.queue_drain import drain

    console = build_default_console(RUNTIME)
    t0 = time.time()
    rep = drain(console, owner=f"unlock-{int(time.time())}", limit=limit)
    print(f"islenen: {len(rep['executed'])} | sure: {round(time.time()-t0,1)}s")
    print("kuyruk:", dict(con.execute("select status,count(*) from missions group by status").fetchall()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 40))