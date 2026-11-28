"""Testler izlenen kuyruk klasörüne (studio/queue) yazmaz: ofis o dosyalardan 'çalışıyor' bilgisi okur,
test artığı gerçek işmiş gibi görünmesin (Q2b). Kuyruk yolu isteyen test kendi değerini ayarlayabilir."""
import pytest


@pytest.fixture(autouse=True)
def _kuyruk_gecici(tmp_path, monkeypatch):
    monkeypatch.setenv("AHOS_QUEUE_DIR", str(tmp_path / "queue"))
    monkeypatch.setenv("AHOS_EVENTS_PATH", str(tmp_path / "queue" / "events.jsonl"))
    yield
