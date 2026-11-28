"""Testler izlenen kuyruk klasörüne (studio/queue) yazmaz: ofis o dosyalardan 'çalışıyor' bilgisi okur,
test artığı gerçek işmiş gibi görünmesin (Q2b). Kuyruk yolu isteyen test kendi değerini ayarlayabilir."""
import pytest


@pytest.fixture(autouse=True)
def _kuyruk_gecici(tmp_path, monkeypatch):
    monkeypatch.setenv("AHOS_QUEUE_DIR", str(tmp_path / "queue"))
    monkeypatch.setenv("AHOS_EVENTS_PATH", str(tmp_path / "queue" / "events.jsonl"))
    # Motor testleri kısa sentetik bölümlerle tam pencere render eder (teslim değil): süre kapısı (V2) test_episode_length.py'de ayrıca ölçülür.
    monkeypatch.setenv("AHOS_ALLOW_SHORT", "1")
    yield
