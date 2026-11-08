"""V5 GÖREV 013 — İşçi durum makinesi (10 durum) ve gerekçeli türetme.

Kurallar:
- Durum **yalnız gözlenen kayıttan** türetilir; süsleme/iyimserlik yoktur.
- Bilinmeyen işçi "boşta" değil "çevrimdışı + kayıt yok" olur (dürüst boşluk).
- Öğrenme/araştırma durumu üretim sayılmaz; yalnız gerçek adım olayı iş sayılır.
- Kalıcı kayıt: `runtime/worker-states.json` (açık olaylar); türetilmiş durum
  her okumada yeniden hesaplanır, dosyaya yazılmaz.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

STATES = ("working", "researching", "learning", "reviewing", "collaborating",
          "waiting_dependency", "waiting_approval", "blocked", "idle", "offline")

LABELS = {
    "working": "çalışıyor",
    "researching": "araştırıyor",
    "learning": "öğreniyor",
    "reviewing": "gözden geçiriyor",
    "collaborating": "iş birliğinde",
    "waiting_dependency": "bağımlılık bekliyor",
    "waiting_approval": "onay bekliyor",
    "blocked": "engellendi",
    "idle": "boşta",
    "offline": "çevrimdışı",
}

# Son gerçek aktivite bu penceredeyse "boşta" (çalışmıyor ama ayakta).
IDLE_WINDOW_SECONDS = 24 * 60 * 60
# Açık olarak yazılmış olay durumu bu süre boyunca türetilmiş durumdan önceliklidir.
RECORDED_TTL_SECONDS = 30 * 60


def _path(runtime) -> Path:
    return Path(runtime) / "worker-states.json"


def _load(runtime) -> dict:
    try:
        data = json.loads(_path(runtime).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _parse(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    # `set_state` yerel saat yazar; saat dilimi yoksa yerel kabul et.
    return stamp.astimezone() if stamp.tzinfo is None else stamp


def _age_seconds(stamp: datetime | None, now: datetime) -> float | None:
    if stamp is None:
        return None
    return max(0.0, (now - stamp).total_seconds())


def set_state(runtime, worker: str, state: str, *, note: str = "") -> dict:
    """Açık olay kaydı. Yalnız gerçek bir olaydan sonra çağrılmalıdır."""

    if state not in STATES:
        raise ValueError(f"invalid worker state: {state}")
    data = _load(runtime)
    record = {"worker": str(worker), "state": state, "note": str(note)[:200],
              "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    data[str(worker)] = record
    path = _path(runtime)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def get_state(runtime, worker: str) -> dict:
    return _load(runtime).get(str(worker)) or {
        "worker": str(worker), "state": "offline", "note": "kayıt yok", "updated_at": ""}


def derive_from_event(runtime, worker: str, *, event: str, ok: bool = True,
                      note: str = "") -> dict:
    """Gözlenen olaydan durum türetir; bilinmeyen olay boşta sayılır."""

    mapping = {"mission": "working", "research": "researching",
               "learning": "learning", "review": "reviewing",
               "collaboration": "collaborating", "dependency": "waiting_dependency",
               "approval": "waiting_approval", "blocked": "blocked", "idle": "idle"}
    state = mapping.get(str(event), "idle")
    if not ok and state == "working":
        state = "blocked"
    return set_state(runtime, worker, state, note=note or event)


def load_all(runtime) -> dict:
    """Tek okumada tüm açık kayıtlar (81 işçi için 81 dosya okumasını önler)."""

    return _load(runtime)


def derive(runtime, worker: str, *, observed_task: str = "",
           last_active: str = "", now: datetime | None = None,
           recorded: dict | None = None) -> dict:
    """İşçinin dürüst durumu: gözlem > taze açık kayıt > son aktivite > yok.

    Dönüş: state (İngilizce kanonik), label (Türkçe), reason (gerekçe),
    source (observed|recorded|metric|none), stale, unknown.
    """

    worker = str(worker)
    now = now or datetime.now(timezone.utc)
    if recorded is None:
        recorded = _load(runtime).get(worker)
    record_age = _age_seconds(_parse((recorded or {}).get("updated_at", "")), now)
    metric_age = _age_seconds(_parse(last_active), now)

    if observed_task:
        return {"worker": worker, "state": "working", "label": LABELS["working"],
                "reason": "gerçek adım olayı (180 sn içinde)", "source": "observed",
                "stale": False, "unknown": False, "updated_at": (recorded or {}).get(
                    "updated_at", ""), "active_task": observed_task}

    if recorded and record_age is not None and record_age <= RECORDED_TTL_SECONDS:
        state = str(recorded.get("state") or "idle")
        if state in STATES:
            return {"worker": worker, "state": state, "label": LABELS[state],
                    "reason": str(recorded.get("note") or "açık olay kaydı"),
                    "source": "recorded", "stale": False, "unknown": False,
                    "updated_at": str(recorded.get("updated_at") or ""),
                    "active_task": ""}

    if metric_age is not None:
        if metric_age <= IDLE_WINDOW_SECONDS:
            return {"worker": worker, "state": "idle", "label": LABELS["idle"],
                    "reason": "son gözlenen koşu %d dk önce" % round(metric_age / 60),
                    "source": "metric", "stale": False, "unknown": False,
                    "updated_at": str(last_active), "active_task": ""}
        return {"worker": worker, "state": "offline", "label": LABELS["offline"],
                "reason": "son gözlenen koşu %.1f gün önce" % (metric_age / 86400),
                "source": "metric", "stale": True, "unknown": False,
                "updated_at": str(last_active), "active_task": ""}

    return {"worker": worker, "state": "offline", "label": LABELS["offline"],
            "reason": "çalışma kaydı yok", "source": "none", "stale": True,
            "unknown": True, "updated_at": "", "active_task": ""}


def counts(records: list[dict], *, key: str = "state") -> dict:
    """Durum sayımı: 10 durumun tamamı için anahtar üretir (sıfırlar dahil)."""

    result = {state: 0 for state in STATES}
    for record in records:
        state = str(record.get(key) or "")
        if state in result:
            result[state] += 1
    return result


def all_states(runtime) -> list[dict]:
    return sorted(_load(runtime).values(), key=lambda row: row.get("worker", ""))
