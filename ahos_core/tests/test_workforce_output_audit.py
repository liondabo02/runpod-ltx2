"""İşçi çıktı denetimi: yalnız doğrulanmış teslimat ürün sayılır."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))


def test_only_verified_delivery_counts_as_product(tmp_path):
    import workforce_output_audit

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    con = sqlite3.connect(runtime / "company-service.db")
    con.execute("create table missions (mission_id text, primary_department text, "
                "status text, result_json text, updated_at text)")
    verified = {"delivery": {"verified": True}, "steps": [
        {"worker_id": "w1", "qa_worker_id": "qa1"}]}
    unverified = {"delivery": {"verified": False}, "steps": [{"worker_id": "w2"}]}
    con.executemany("insert into missions values (?,?,?,?,?)", [
        ("m1", "dep", "completed", json.dumps(verified), "2026-11-07T10:00:00"),
        ("m2", "dep", "completed", json.dumps(unverified), "2026-11-07T11:00:00"),
        ("m3", "dep", "completed", None, "2026-11-07T12:00:00"),
    ])
    con.commit()
    con.close()
    (runtime / "departments.json").write_text(json.dumps({"departments": [
        {"department_id": "dep", "workers": [
            {"worker_id": "w1"}, {"worker_id": "w2"}, {"worker_id": "w3"}]}]}), encoding="utf-8")

    report = workforce_output_audit.audit(runtime)

    assert report["completed_total"] == 3
    assert report["verified_deliveries"] == 1
    assert report["workers_with_verified_output"] == 1
    assert report["workers_without_verified_output"] == 2
    assert report["top_workers"][0]["worker_id"] == "w1"
    assert report["departments"]["dep"] == {"completed": 3, "verified": 1}


def test_qa_proof_file_is_separate_from_metadata_flag(tmp_path):
    import workforce_output_audit

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    proofs = runtime / "artifacts"
    proofs.mkdir()
    qa_path = proofs / "qa-m1.json"
    qa_path.write_text(json.dumps({"passed": True, "functional_verified": True}),
                       encoding="utf-8")
    con = sqlite3.connect(runtime / "company-service.db")
    con.execute("create table missions (mission_id text, primary_department text, "
                "status text, result_json text, updated_at text)")
    flagged = {"delivery": {"verified": True}, "steps": [
        {"worker_id": "producer-1", "qa_worker_id": "qa-1",
         "qa_summary": "QA evidence: " + str(qa_path)}]}
    missing = {"delivery": {"verified": True}, "steps": [
        {"worker_id": "producer-2", "qa_worker_id": "qa-1",
         "qa_summary": "QA evidence: " + str(proofs / "missing.json")}]}
    con.executemany("insert into missions values (?,?,?,?,?)", [
        ("m1", "studio", "completed", json.dumps(flagged), "2026-11-07"),
        ("m2", "studio", "completed", json.dumps(missing), "2026-11-07")])
    con.commit()
    con.close()
    result = workforce_output_audit.audit(runtime, verify_qa_files=True)
    assert result["verified_delivery_flags"] == 2
    assert result["qa_proof_file_pass_missions"] == 1
    assert result["functional_qa_proof_missions"] == 1
    assert result["delivery_flags_without_qa_file_proof"] == 1
    assert result["qa_evidence_checked"] is True


def test_qa_proof_outside_runtime_is_not_trusted(tmp_path):
    import workforce_output_audit
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    external = tmp_path / "other.json"
    external.write_text(json.dumps({"passed": True, "functional_verified": True}),
                        encoding="utf-8")
    assert workforce_output_audit._load_qa_proof(
        {"qa_summary": str(external)}, runtime) == {}
