"""AHOS parça klibi kimliği (diziden bağımsız): doğrulanmış bir parça yalnız AYNI girdilerle üretildiyse yeniden kullanılır.

Süresi tutan klip 'doğru klip' değildir: senaryo, ses, varlık, motor ya da taslak izni değişmişse eski klip ve içindeki
eski içerik teslime girerdi; yeniden kullanılan parça render kapılarından da geçmez. Klibin yanında '<klip>.inputs.json' tutulur:
girdi özeti + klibin kendi özeti + taslak işareti. Kayıt yoksa ya da biri uyuşmuyorsa parça yeniden üretilir (ve kapılardan yeniden geçer)."""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = "ahos.clip_inputs.v1"
ENV_KEYS = ("AHOS_STYLE", "AHOS_ALLOW_ESTIMATED_VOICE")
EPISODE_FILES = ("beat_sheet.json", "voice_manifest.json")
SERIES_FILES = ("series-bible.json", "locations.json", "action_cues.json")


def file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _tree(root, suffix=""):
    out = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        out += [os.path.join(base, f) for f in sorted(files) if f.endswith(suffix)]
    return out


def _referenced(episode_dir):
    """Ses listesinin gösterdiği ses ve ağız dosyaları."""
    try:
        items = json.load(open(os.path.join(episode_dir, "voice_manifest.json"), encoding="utf-8"))["items"]
        return sorted({str(it[k]).replace("\\", "/") for it in items for k in ("wav", "visemes") if it.get(k)})
    except Exception:  # noqa: BLE001 (liste yok/bozuk: listenin kendisi zaten özete girer)
        return []


def fingerprint(episode_dir, bible, series_dir, t0, t1, fps, engine, samples):
    h = hashlib.sha256()

    def add(label, path):
        h.update(label.encode("utf-8") + b"\0")
        h.update(file_sha(path).encode() if os.path.isfile(path) else b"-")
    for path in _tree(HERE, ".py"):                                     # motor kaynakları
        add("tool:" + os.path.relpath(path, HERE).replace(os.sep, "/"), path)
    for name in EPISODE_FILES:
        add("episode:" + name, os.path.join(episode_dir, name))
    for rel in _referenced(episode_dir):
        add("episode:" + rel, os.path.join(episode_dir, rel))
    for name in SERIES_FILES:
        add("series:" + name, os.path.join(series_dir, name))
    assets = os.path.join(series_dir, "assets")
    for path in _tree(assets):                                          # varlık sürümü
        add("asset:" + os.path.relpath(path, assets).replace(os.sep, "/"), path)
    h.update(json.dumps([bible, round(float(t0), 4), round(float(t1), 4), int(fps), engine, samples,
                         [os.environ.get(k, "") for k in ENV_KEYS]], sort_keys=True, default=str).encode("utf-8"))
    return h.hexdigest()


def record_path(clip):
    return clip + ".inputs.json"


def record(clip, inputs, draft=False):
    tmp = record_path(clip) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"schema": SCHEMA, "inputs": inputs, "clip_sha256": file_sha(clip), "draft": bool(draft)}, f)
    os.replace(tmp, record_path(clip))


def forget(clip):
    """Yeniden üretimden önce eski kaydı kaldır: yarıda kalan üretim eski kayıtla 'doğrulanmış' görünmesin."""
    if os.path.exists(record_path(clip)):
        os.remove(record_path(clip))


def reusable(clip, inputs):
    """(yeniden kullanılabilir mi, gerekçe ya da kayıt)."""
    if not os.path.isfile(clip):
        return False, "klip yok"
    try:
        rec = json.load(open(record_path(clip), encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False, "girdi kaydı yok ya da okunamıyor"
    if rec.get("schema") != SCHEMA or rec.get("inputs") != inputs:
        return False, "girdiler değişti (senaryo, ses, varlık, motor ya da ayar)"
    if rec.get("clip_sha256") != file_sha(clip):
        return False, "klip dosyası kayıttan sonra değişti"
    return True, rec
