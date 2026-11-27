"""Ortak görev kaydı (bulut + yerel işçiler aynı kaydı kullanır) ve iş kimliği (work_key).
İKİ KATMAN:
  1) Dosya kaydı: studio/ledger/<job_id>.json {job_id, machine, token, src_hash, status, started, heartbeat, result_sha256, result}.
     claim/heartbeat/complete/fail tek bir SQLite yazma kilidi altında çalışır: AYNI DOSYA SİSTEMİNDEKİ süreçler arasında atomiktir.
     Aynı görev + aynı kaynak sürümü taze nabızla çalışıyorsa makine adı ne olursa olsun REDDEDİLİR (aynı makinede ikinci süreç dahil).
     Nabız kesilmişse devralınır; her claim yeni 'token' üretir, token verilen eski sahip artık nabız/tamamlama yazamaz.
     SINIR: kayıt dosya köprüsüyle başka makineye kopyalanıyorsa makineler arası atomiklik YOKTUR.
  2) Medya üretim işlerinde TEK YETKİLİ DAĞITICI kuyruktur (studio_media_queue.MediaQueue, tek SQLite). Kuyruk mükerrer işi
     work_key ile tanır: aynı yetenek + aynı üretim girdisi (bölüm kimliği gibi geçici alanlar hariç) + aynı onaylı üst çıktılar.
Tamamlanan iş: result_sha256 ile doğrulanmadan 'DONE' sayılmaz."""
import contextlib, hashlib, json, os, sqlite3, time, uuid

TTL = 600.0
# İşin içeriğini değiştirmeyen alanlar. shotplan_sha256 bütün sahne listesinin özetidir; bu işin girdisi payload'daki scene_plan dilimidir.
VOLATILE = ("episode_id", "shotplan_sha256", "creative_status", "production_ready")


def work_key(capability, payload, inputs=()):
    """İşin içerik kimliği. inputs: (üst_görev, dosya_adı, sha256) üçlüleri."""
    body = {"capability": capability, "payload": {k: v for k, v in payload.items() if k not in VOLATILE},
            "inputs": sorted(list(x) for x in inputs)}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _path(root, job_id):
    name = job_id.replace("/", "_")
    if name != job_id:                      # 'a/b' ile 'a_b' aynı dosyaya düşmesin
        name += "~" + hashlib.sha256(job_id.encode("utf-8")).hexdigest()[:8]
    return os.path.join(root, "studio", "ledger", name + ".json")


@contextlib.contextmanager
def _locked(root):
    """Süreçler arası yazma kilidi (Windows+Linux; süreç ölürse kilit kendiliğinden bırakılır)."""
    folder = os.path.join(root, "studio", "ledger"); os.makedirs(folder, exist_ok=True)
    db = sqlite3.connect(os.path.join(folder, ".lock.sqlite3"), timeout=30, isolation_level=None)
    try:
        db.execute("BEGIN EXCLUSIVE")
        yield
    finally:
        db.close()                          # kapatma açık işlemi geri alır ve kilidi bırakır


def _load(root, job_id):
    p = _path(root, job_id)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _save(root, rec):
    p = _path(root, rec["job_id"]); os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def claim(root, job_id, machine, src_hash, now=None, ttl=None):
    """-> {'ok': bool, 'action': 'RUN'|'RESUME'|'DONE'|'REJECT', 'owner', 'why', 'token' (yalnız RUN/RESUME)}"""
    ttl = TTL if ttl is None else ttl
    with _locked(root):
        now = time.time() if now is None else now; rec = _load(root, job_id)
        if rec and rec.get("src_hash") == src_hash and rec["status"] == "done" and rec.get("result") and os.path.exists(rec["result"]) \
                and sha256_file(rec["result"]) == rec.get("result_sha256"):
            return {"ok": True, "action": "DONE", "owner": rec["machine"], "why": "sonuç doğrulandı; yeniden çalıştırma yok"}
        if rec and rec["status"] == "running" and now - rec["heartbeat"] <= ttl and rec.get("src_hash") == src_hash:
            return {"ok": False, "action": "REJECT", "owner": rec["machine"], "why": f"aynı görev {rec['machine']} makinesinde çalışıyor (nabız {now - rec['heartbeat']:.0f} sn önce)"}
        action = "RESUME" if rec and rec["status"] == "running" else "RUN"
        token = uuid.uuid4().hex
        _save(root, {"job_id": job_id, "machine": machine, "token": token, "src_hash": src_hash, "status": "running", "started": now, "heartbeat": now, "result": None, "result_sha256": None})
    why = "başlatıldı" if action == "RUN" else "devralındı (önceki nabız bayat ya da kaynak sürümü farklı)"
    return {"ok": True, "action": action, "owner": machine, "token": token, "why": why}


def _owned(rec, machine, token):
    """Yalnız çalışan işin sahibi yazar. token verilmişse eşleşmeli (devralınmış eski süreç dışarıda kalır)."""
    return bool(rec) and rec["status"] == "running" and rec["machine"] == machine and (token is None or rec.get("token") == token)


def heartbeat(root, job_id, machine, now=None, token=None):
    with _locked(root):
        rec = _load(root, job_id)
        if not _owned(rec, machine, token):
            return False
        rec["heartbeat"] = time.time() if now is None else now; _save(root, rec); return True


def complete(root, job_id, machine, result_path, now=None, token=None):
    with _locked(root):
        rec = _load(root, job_id)
        if not _owned(rec, machine, token):
            return False
        rec.update(status="done", heartbeat=time.time() if now is None else now, result=result_path, result_sha256=sha256_file(result_path)); _save(root, rec); return True


def fail(root, job_id, machine, why, token=None):
    with _locked(root):
        rec = _load(root, job_id)
        if not _owned(rec, machine, token):
            return False
        rec.update(status="failed", why=why); _save(root, rec); return True
