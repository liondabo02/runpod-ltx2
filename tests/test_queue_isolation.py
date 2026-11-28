"""Q2b: testler gerçek studio/queue klasörüne progress.json / events.jsonl yazmaz."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import showrunner, worker_events


def test_steplog_yazimi_gecici_klasore_gider(tmp_path):
    real = os.path.join(ROOT, "studio", "queue", "progress.json")
    before = os.path.getmtime(real) if os.path.exists(real) else None
    log = showrunner.StepLog()
    log.append({"worker": "w1", "status": "OK"})
    tmp = os.path.join(os.environ["AHOS_QUEUE_DIR"], "progress.json")
    assert os.path.exists(tmp), "progress.json geçici klasöre yazılmadı"
    after = os.path.getmtime(real) if os.path.exists(real) else None
    assert before == after, "test gerçek kuyruk klasörüne yazdı"


def test_olay_yolu_gecici_klasorde():
    assert os.path.realpath(worker_events.path()).startswith(os.path.realpath(os.environ["AHOS_QUEUE_DIR"]))


def test_bilerek_bozma_varsayilan_yol_gercek_klasor(monkeypatch):
    """Ortam değişkeni yoksa üretim davranışı değişmedi: gerçek klasör kullanılır."""
    monkeypatch.delenv("AHOS_EVENTS_PATH", raising=False)
    assert worker_events.path() == os.path.join(ROOT, "studio", "queue", "events.jsonl")
