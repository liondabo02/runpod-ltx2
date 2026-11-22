r"""Stüdyoya iş ekler (komut yaz, işçiler sırayla yapsın).
python tools\studio_enqueue.py --command "Aden ve Kaan ... yeni bölüm" --series-id aden --render-seconds -1"""
import argparse, json, os, time, uuid
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Q = os.path.join(ROOT, "studio", "queue")
def enqueue(command, series_id=None, seconds=480, render_seconds=12):
    os.makedirs(Q, exist_ok=True)
    jid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    job = {"id": jid, "command": command, "series_id": series_id, "seconds": seconds, "render_seconds": render_seconds, "state": "pending"}
    json.dump(job, open(os.path.join(Q, jid + ".pending.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return jid
if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--command", required=True); p.add_argument("--series-id")
    p.add_argument("--seconds", type=int, default=480); p.add_argument("--render-seconds", type=int, default=12)
    a = p.parse_args(); print("Kuyruğa eklendi:", enqueue(a.command, a.series_id, a.seconds, a.render_seconds))
