"""Ar-Ge departmanı: sahip orada olmasa da sürekli iyileştirme.

Her turda (varsayılan 30 dakikada bir) şunları yapar:

1. **Ölçer** — departman başarı oranları, engelli görev nedenleri, işçi karnesi.
2. **Teşhis eder** — en zayıf 3 departmanı ve baskın hata sınıfını belirler.
3. **Ders yazar** — her zayıf departman için müfredat maddesi üretir ve bilgi
   ağına (skill cards) aktarır; böylece sonraki görevlerde prompt'a girer.
4. **İş açar** — zayıf departmana küçük, doğrulanabilir bir Ar-Ge görevi kuyruğa
   bırakır (kuyrukta bekleyen işi varsa tekrar açmaz).

Kurallar: tur başına en fazla 2 görev, en fazla 3 müfredat; ağ/model çağrısı yok
(deterministik, ücretsiz). Böylece 7/24 çalışabilir.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

INTERVAL_SECONDS = 1800  # 30 dakika

GAME_OBJECTIVE = (
    "Oyun Ar-Ge: sokak oyunlarında (seksek, beş taş, yakar top, yerden yüksek, "
    "yedi kule, saklambaç) 3 iyileştirme öner: zorluk dengesi, erişilebilirlik, performans"
)
STATE_FILE = "arge-state.json"


@dataclass
class ArgeResult:
    ran: bool
    weakest: tuple[str, ...] = ()
    lessons: int = 0
    queued: tuple[str, ...] = ()
    reason: str = ""


def _state_path(runtime: Path) -> Path:
    return runtime / STATE_FILE


def _load_state(runtime: Path) -> dict:
    path = _state_path(runtime)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(runtime: Path, payload: dict) -> None:
    try:
        _state_path(runtime).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def measure(runtime: Path) -> tuple[dict[str, float], dict[str, Counter]]:
    """Departman başarı oranı ve engel nedenleri."""

    rates: dict[str, float] = {}
    reasons: dict[str, Counter] = defaultdict(Counter)

    ledger = runtime / "worker-metrics.jsonl"
    stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines()[-4000:]:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            dept = str(row.get("department") or "?")
            stats[dept][0] += 1
            stats[dept][1] += 1 if row.get("success") else 0
    for dept, (runs, ok) in stats.items():
        if runs:
            rates[dept] = ok / runs

    db = runtime / "company-service.db"
    if db.exists():
        try:
            with sqlite3.connect(db) as con:
                for mission, error in con.execute(
                    "select mission_id, last_error from missions where status='blocked'"
                ):
                    dept = mission.split("-")[1] if "-" in mission else "?"
                    text = (error or "").lower()
                    if "kilit" in text:
                        key = "kilit"
                    elif "timeout" in text or "zaman aşımı" in text:
                        key = "zaman aşımı"
                    elif "qa failed" in text or "unverified" in text:
                        key = "QA"
                    elif "executor" in text or "yürütücü" in text:
                        key = "yürütücü"
                    elif "dosya yok" in text or "hedef" in text:
                        key = "hedef dosya"
                    else:
                        key = "diğer"
                    reasons[dept][key] += 1
        except sqlite3.Error:
            pass
    return rates, reasons


LESSON_TEMPLATES = {
    "QA": "Geçmişte bu departmanda kabul kapısı reddi görüldü: teslimden önce `tools/check_offline.py` çalıştır ve dosya değişikliğini doğrula.",
    "zaman aşımı": "Geçmişte zaman aşımı görüldü: yanıtı kısa tut (<=700 token), tek dosya odaklı çalış, gerekiyorsa işi iki adıma böl.",
    "yürütücü": "Geçmişte yürütücü bağlı değildi: proje bağlı olmayan işlerde belge yürütücüsünü kullan, çıktı dosyası yoksa başarısız say.",
    "hedef dosya": "Geçmişte hedef dosya bulunamadı: yama uygulamadan önce yolun var olduğunu doğrula; dosya adını uydurma.",
    "kilit": "Geçmişte proje kilidi engelledi: görev öncesi kilidi ve sahibini kontrol et; sahipsiz kilidi serbest bırak.",
    "diğer": "Geçmişte sınıflandırılamayan hata görüldü: hatayı tek adımda yeniden üret ve nedeni yaz.",
}


def write_lessons(runtime: Path, weakest: list[str], reasons: dict[str, Counter]) -> int:
    """Zayıf departmanlar için müfredat kartı üretir ve bilgi ağına aktarır."""

    if not weakest:
        return 0
    try:
        from . import skills
    except Exception:  # noqa: BLE001
        return 0

    inbox = runtime / "knowledge" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    written = 0
    for dept in weakest[:3]:
        top = reasons.get(dept, Counter()).most_common(1)
        cause = top[0][0] if top else "diğer"
        lesson = LESSON_TEMPLATES.get(cause, LESSON_TEMPLATES["diğer"])
        body = (
            f"# Ar-Ge dersi · {dept}\n\n"
            f"Baskın hata: {cause}\n\n"
            f"## Kural\n- {lesson}\n\n"
            f"## Uygulama\n- Görev bitince çıktı dosyasını ve kabul kapısını kontrol et.\n"
        )
        path = inbox / f"arge-{dept}-{int(time.time())}.md"
        try:
            path.write_text(body, encoding="utf-8")
            result = skills.learn(runtime, path, use_model=False)
            written += int(result.get("cards") or 0)
        except Exception:  # noqa: BLE001
            continue
    return written


def queue_research(runtime: Path, weakest: list[str]) -> tuple[str, ...]:
    """Zayıf departmanlara küçük Ar-Ge görevi bırakır (kuyruk doluysa atlar)."""

    if not weakest:
        return ()
    try:
        from .autonomous_company import PersistentMissionQueue, QueueStatus
    except Exception:  # noqa: BLE001
        return ()

    queue = PersistentMissionQueue(runtime / "company-service.db")
    pending = set()
    try:
        for mission in queue.list(statuses=(QueueStatus.PENDING,)):
            pending.add(getattr(mission, "primary_department", ""))
    except Exception:  # noqa: BLE001
        return ()

    created: list[str] = []
    for dept in weakest[:2]:
        if dept in pending:
            continue
        mission_id = f"CMD-{dept}-arge-{int(time.time())}"
        objective = (
            GAME_OBJECTIVE if dept == "oyun" else
            f"{dept} departmanı için Ar-Ge: son 10 görevin hatasını özetle, "
            "3 somut iyileştirme ve 1 ölçüm kriteri yaz"
        )
        try:
            queue.enqueue(
                mission_id=mission_id,
                objective=objective,
                primary_department=dept,
                max_attempts=1,
                replace_existing=False,
            )
            created.append(mission_id)
        except Exception:  # noqa: BLE001
            continue
    return tuple(created)


def tick(runtime_dir: str | Path, *, force: bool = False, now: float | None = None) -> ArgeResult:
    """Ar-Ge turu; varsayılan 30 dakikada bir çalışır."""

    runtime = Path(runtime_dir)
    now = time.time() if now is None else now
    state = _load_state(runtime)
    last = float(state.get("last_run") or 0)
    if not force and now - last < INTERVAL_SECONDS:
        return ArgeResult(ran=False, reason="bekleme süresi dolmadı")

    rates, reasons = measure(runtime)
    # En zayıf: başarı oranı düşük ve yeterli koşusu olan departmanlar
    ranked = sorted(
        ((dept, rate) for dept, rate in rates.items() if dept != "?"),
        key=lambda item: item[1],
    )
    weakest = [dept for dept, _ in ranked[:3]]

    lessons = write_lessons(runtime, weakest, reasons)
    try:
        queued = queue_research(runtime, weakest)
    except Exception:  # noqa: BLE001 - kuyruk hatası Ar-Ge turunu durdurmasın
        queued = ()

    _save_state(
        runtime,
        {
            "last_run": now,
            "last_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
            "weakest": weakest,
            "rates": {dept: round(rate, 3) for dept, rate in rates.items()},
            "lessons": lessons,
            "queued": list(queued),
        },
    )
    return ArgeResult(ran=True, weakest=tuple(weakest), lessons=lessons, queued=queued)
