"""CEO chat and the closed knowledge network."""

from __future__ import annotations

import json
import threading
import urllib.request

from ahos import ceo, knowledge
from ahos.office_server import serve


def _runtime(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "daemon-state.json").write_text(
        json.dumps({"status": "running", "executor_mode": "model"}), encoding="utf-8"
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "mimari.md").write_text(
        "# Mimari\n\nServis katmanı SQLite kuyruğu kullanır. Kuyruk sahipliği "
        "kira ile korunur ve süresi geçen kira geri alınır.\n\n"
        "## Test\n\nHer yama kabul testinden geçmelidir.",
        encoding="utf-8",
    )
    (docs / "react.md").write_text(
        "React bileşenleri küçük tutulmalı; durum yönetimi tek yerde olmalı.",
        encoding="utf-8",
    )
    return runtime, docs


def test_knowledge_is_indexed_and_searchable(tmp_path) -> None:
    runtime, docs = _runtime(tmp_path)

    added = knowledge.add(runtime, docs)
    hits = knowledge.search(runtime, "kuyruk kira sahipliği")

    assert added["documents"] == 2
    assert hits and hits[0]["name"] == "mimari.md"
    assert "kira" in hits[0]["text"].lower()


def test_knowledge_add_is_idempotent(tmp_path) -> None:
    runtime, docs = _runtime(tmp_path)
    knowledge.add(runtime, docs)

    again = knowledge.add(runtime, docs)

    assert again["documents"] == 0
    assert knowledge.stats(runtime)["documents"] == 2


def test_knowledge_context_is_prompt_ready(tmp_path) -> None:
    runtime, docs = _runtime(tmp_path)
    knowledge.add(runtime, docs)

    block = knowledge.context(runtime, "kabul testi kuyruk")

    assert "Bilgi ağından" in block
    assert "mimari.md" in block


def test_ceo_answers_and_records_the_thread(tmp_path, monkeypatch) -> None:
    runtime, _docs = _runtime(tmp_path)
    monkeypatch.delenv("AHOS_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("AHOS_LLM_API_KEY", raising=False)
    monkeypatch.delenv("AHOS_LLM_MODEL", raising=False)

    result = ceo.answer(runtime, "sistemin durumu nedir")

    assert result["reply"]
    assert "teslim" in result["reply"].lower()
    transcript = ceo.thread(runtime)
    assert transcript[-1]["role"] == "ceo"
    assert transcript[-2]["text"].startswith("sistemin")


def test_ceo_routes_a_work_request(tmp_path, monkeypatch) -> None:
    runtime, _docs = _runtime(tmp_path)
    monkeypatch.delenv("AHOS_LLM_BASE_URL", raising=False)

    result = ceo.answer(runtime, "çocuklar için yeni bir oyun yapmak istiyorum")

    assert result["routed"] is not None
    assert result["tasks"] >= 1
    assert list((runtime / "ideas").glob("*.json")), "fikir kaydedilmeli"


def test_office_exposes_the_ceo_endpoint(tmp_path, monkeypatch) -> None:
    runtime, _docs = _runtime(tmp_path)

    def fake_answer(runtime_dir, message):
        return {"reply": "merhaba", "routed": None, "tasks": 0, "mode": "test"}

    monkeypatch.setattr(ceo, "answer", fake_answer)
    server = serve(runtime, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        request = urllib.request.Request(
            f"{base}/api/ceo",
            data=json.dumps({"message": "selam"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["reply"] == "merhaba"
    finally:
        server.shutdown()
        server.server_close()
