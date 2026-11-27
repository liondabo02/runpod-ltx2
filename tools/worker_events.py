"""Gerçek işçi olay kaydı. Ofis 'çalışıyor' bilgisini YALNIZ buradan üretir.

Satır: {"at": epoch, "job": id, "worker": id, "kind": start|note|done|failed, "text": str}
Yalnız bir iş kimliği (AHOS_JOB_ID) varken yazar: testler ve elle çağrılar izlenen klasöre dokunmaz.
Kayıt hatası üretimi durdurmaz."""
import json, os, time
from contextlib import contextmanager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KINDS = ("start", "note", "done", "failed")
_stack = []


def path():
    return os.environ.get("AHOS_EVENTS_PATH") or os.path.join(ROOT, "studio", "queue", "events.jsonl")


def emit(worker, kind, text="", job=None):
    job = job or os.environ.get("AHOS_JOB_ID")
    if not job or kind not in KINDS:
        return False
    row = {"at": round(time.time(), 3), "job": job, "worker": worker, "kind": kind, "text": str(text)[:300]}
    try:
        os.makedirs(os.path.dirname(path()), exist_ok=True)
        with open(path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def note(text):
    """O anda çalışan işçinin ara adımı (örn. model çağrısı, seslendirilen satır)."""
    if _stack:
        emit(_stack[-1], "note", text)


class _Act:
    result = None

    def done(self, text=""):
        self.result = ("done", text)

    def failed(self, text=""):
        self.result = ("failed", text)


@contextmanager
def working(worker, text):
    """İşçi gerçekten çalışırken start; çıkışta mutlaka done/failed. Sonuç bildirilmezse başarı SAYILMAZ."""
    act = _Act()
    emit(worker, "start", text)
    _stack.append(worker)
    try:
        yield act
    except BaseException as e:
        act.result = ("failed", "%s: %s" % (type(e).__name__, str(e)[:200]))
        raise
    finally:
        _stack.pop()
        kind, msg = act.result or ("failed", "sonuç bildirilmedi")
        emit(worker, kind, msg)


def read(limit=2000):
    try:
        with open(path(), encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            r = json.loads(ln)
            if isinstance(r, dict) and r.get("kind") in KINDS and r.get("worker") and r.get("job"):
                out.append(r)
        except ValueError:
            continue   # yarım yazılmış satır
    return out
