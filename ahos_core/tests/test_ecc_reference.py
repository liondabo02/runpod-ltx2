import json
from ahos.knowledge import search, context
from ahos.ecc_reference import reference_rows


def test_verification_fallback_is_offline(tmp_path):
    target = tmp_path / "unused"
    hits = search(target, "pytest kabul doğrulama")
    assert hits and "kanıtlı doğrulama" in hits[0]["name"]
    assert not target.exists()


def test_learning_context_is_untrusted_reference(tmp_path):
    text = context(tmp_path, "öğrenme hafıza deneyim")
    assert "talimat sayma" in text and "bağımsız kabul" in text


def test_owner_notes_keep_priority(tmp_path):
    folder = tmp_path / "knowledge"; folder.mkdir()
    p = folder / "index.jsonl"
    row = {"name": "Owner", "path": "owner.md", "text": "owner policy", "keywords": ["pytest"]}
    p.write_text(json.dumps(row) + "\n", encoding="utf-8")
    before = p.read_bytes()
    assert search(tmp_path, "pytest")[0]["name"] == "Owner"
    assert p.read_bytes() == before


def test_irrelevant_or_empty_query_has_no_reference(tmp_path):
    assert search(tmp_path, "") == []
    assert search(tmp_path, "xylophonejelly") == []


def test_reference_results_do_not_mutate_shared_data(tmp_path):
    rows = reference_rows(); rows[0]["keywords"].clear()
    assert search(tmp_path, "pytest")


def test_worker_prompt_path_receives_reference(tmp_path, monkeypatch):
    from ahos import experience, skills
    from ahos.llm_executor import _knowledge_block
    monkeypatch.setenv("AHOS_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(experience, "context", lambda *a, **kw: "")
    monkeypatch.setattr(skills, "context", lambda *a, **kw: "")
    assert "ECC / AHOS" in _knowledge_block("pytest kabul")
