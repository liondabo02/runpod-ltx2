"""Ortak görev kaydı (bulut + yerel işçiler aynı kaydı kullanır). Bir görev aynı anda yalnız bir makinede çalışır.
Kayıt: studio/ledger/<job_id>.json  {job_id, machine, src_hash, status, started, heartbeat, result_sha256, result}
Kurallar: claim -> aynı iş başka makinede taze nabızla (ttl içinde) çalışıyorsa REDDEDİLİR; nabız kesilmişse (bağlantı koptu) devralınabilir ve
önceki sonuç dosyası doğrulanmışsa iş yeniden yapılmaz (resume). Tamamlanan iş: result_sha256 ile doğrulanmadan 'verified' olmaz.
Not: makineler arası kayıt aktarımı dosya köprüsüyle (commit/stage) yapılır; atomik kilit yoktur — çakışma riski claim'in taze-nabız kontrolü ve
iş kimliğinin kaynak sha'sını içermesiyle azaltılır."""
import hashlib, json, os, time

TTL = 600.0


def _path(root, job_id):
    return os.path.join(root, "studio", "ledger", job_id.replace("/", "_") + ".json")


def _load(root, job_id):
    p = _path(root, job_id)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def _save(root, rec):
    p = _path(root, rec["job_id"]); os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"; json.dump(rec, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(tmp, p)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def claim(root, job_id, machine, src_hash, now=None, ttl=TTL):
    """-> {'ok': bool, 'action': 'RUN'|'RESUME'|'DONE'|'REJECT', 'owner', 'why'}"""
    now = time.time() if now is None else now; rec = _load(root, job_id)
    if rec and rec.get("src_hash") == src_hash and rec["status"] == "done" and rec.get("result") and os.path.exists(rec["result"]) \
            and sha256_file(rec["result"]) == rec.get("result_sha256"):
        return {"ok": True, "action": "DONE", "owner": rec["machine"], "why": "sonuç doğrulandı; yeniden çalıştırma yok"}
    if rec and rec["status"] == "running" and rec["machine"] != machine and now - rec["heartbeat"] <= ttl and rec.get("src_hash") == src_hash:
        return {"ok": False, "action": "REJECT", "owner": rec["machine"], "why": f"aynı görev {rec['machine']} makinesinde çalışıyor (nabız {now - rec['heartbeat']:.0f} sn önce)"}
    action = "RESUME" if rec and rec["status"] == "running" else "RUN"
    _save(root, {"job_id": job_id, "machine": machine, "src_hash": src_hash, "status": "running", "started": now, "heartbeat": now, "result": None, "result_sha256": None})
    return {"ok": True, "action": action, "owner": machine, "why": "devralındı (önceki nabız bayat)" if action == "RESUME" else "başlatıldı"}


def heartbeat(root, job_id, machine, now=None):
    rec = _load(root, job_id)
    if not rec or rec["machine"] != machine:
        return False
    rec["heartbeat"] = time.time() if now is None else now; _save(root, rec); return True


def complete(root, job_id, machine, result_path, now=None):
    rec = _load(root, job_id)
    if not rec or rec["machine"] != machine:
        return False
    rec.update(status="done", heartbeat=time.time() if now is None else now, result=result_path, result_sha256=sha256_file(result_path)); _save(root, rec); return True


def fail(root, job_id, machine, why):
    rec = _load(root, job_id)
    if rec and rec["machine"] == machine:
        rec.update(status="failed", why=why); _save(root, rec)
