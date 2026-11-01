"""Departmanlar arası iş birliği — tek istek, çok departman.

AgentSpace / Munder Difflin'deki "ajanlar birlikte çalışır" fikrinin AHOS
karşılığı: bir istek, niyet analiziyle **departman parçalarına** bölünür; her
parça kendi departmanına görev olarak düşer ve aynı **bilet** altında izlenir.

- `split(objective)`   : isteği departman parçalarına ayırır (niyet + anahtar kelime)
- `launch(runtime, ...)`: parçaları kuyruğa bırakır, ortak bilet açar
- `status(runtime, ticket)`: parçaların durumunu tek yerde toplar
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

# Departman → o departmanın işe katkısı (parça metni)
CONTRIBUTIONS = {
    "oyun": "oyun tarafı: mekanik/akış değişikliğini uygula",
    "software": "yazılım tarafı: teknik uygulamayı ve testleri yap",
    "creative": "stüdyo tarafı: görsel/ses/senaryo üret",
    "data": "veri tarafı: ölçüm kriteri ve rapor hazırla",
    "quality": "kalite tarafı: kabul kriterlerini ve test planını yaz",
    "hukuk": "hukuk tarafı: riskleri ve yasal alternatifi yaz",
    "marketing": "pazarlama tarafı: tanıtım metni ve planı hazırla",
    "research": "araştırma tarafı: rakip/benchmark incelemesi yap",
    "finance": "finans tarafı: maliyet ve bütçe etkisini çıkar",
    "guvenlik": "güvenlik tarafı: risk ve izinleri denetle",
}

KEYWORDS = {
    "oyun": ("oyun", "mipiluna", "level", "bölüm", "sokak"),
    "software": ("kod", "yazılım", "hata", "api", "sayfa", "uygulama", "apk"),
    "creative": ("video", "ses", "dublaj", "jenerik", "görsel", "tasarım", "senaryo"),
    "data": ("veri", "rapor", "analiz", "metrik", "istatistik"),
    "quality": ("test", "kalite", "kabul", "doğrulama"),
    "hukuk": ("telif", "lisans", "kvkk", "marka", "sözleşme", "hukuk"),
    "marketing": ("pazarlama", "tanıtım", "reklam", "sosyal medya"),
    "research": ("araştır", "rakip", "benchmark", "incele"),
    "finance": ("bütçe", "maliyet", "fatura", "fiyat"),
    "guvenlik": ("güvenlik", "izin", "şifre", "denetim"),
}

MAX_DEPARTMENTS = 3


@dataclass(frozen=True)
class Part:
    department: str
    objective: str


@dataclass
class Collaboration:
    ticket: str
    objective: str
    parts: list[Part] = field(default_factory=list)
    missions: list[str] = field(default_factory=list)


def split(objective: str, *, limit: int = MAX_DEPARTMENTS) -> list[Part]:
    """İsteği departman parçalarına ayırır (en az bir parça)."""

    low = objective.casefold()
    scores: list[tuple[int, str]] = []
    for department, words in KEYWORDS.items():
        score = sum(1 for word in words if word in low)
        if score:
            scores.append((score, department))
    scores.sort(key=lambda pair: (-pair[0], pair[1]))

    chosen = [department for _, department in scores[:limit]]
    if not chosen:
        chosen = ["genel"]

    parts: list[Part] = []
    for department in chosen:
        note = CONTRIBUTIONS.get(department, "genel yürütme: isteği en küçük adıma böl")
        parts.append(Part(department=department, objective=f"{objective} · {note}"))
    return parts


def launch(runtime_dir: str | Path, objective: str, *, ticket: str | None = None) -> Collaboration:
    """Parçaları kuyruğa bırakır; ortak biletle izlenebilir hale getirir."""

    runtime = Path(runtime_dir)
    stamp = int(time.time())
    ticket = ticket or f"COL-{stamp}"
    collaboration = Collaboration(ticket=ticket, objective=objective, parts=split(objective))

    try:
        from .autonomous_company import PersistentMissionQueue

        queue = PersistentMissionQueue(runtime / "company-service.db")
        for index, part in enumerate(collaboration.parts, start=1):
            mission_id = f"CMD-{part.department}-collab-{stamp}-{index}"
            queue.enqueue(
                mission_id=mission_id,
                objective=part.objective,
                primary_department=part.department,
                max_attempts=2,
                replace_existing=True,
            )
            collaboration.missions.append(mission_id)
    except Exception:  # noqa: BLE001 - kuyruk isteğe bağlı
        pass

    record = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ticket": ticket,
        "objective": objective,
        "parts": [{"department": part.department, "mission": mission}
                  for part, mission in zip(collaboration.parts, collaboration.missions)],
    }
    path = runtime / "collaborations.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return collaboration


def status(runtime_dir: str | Path, ticket: str) -> dict:
    """Bir iş birliği biletinin parçalarını tek yerde toplar."""

    runtime = Path(runtime_dir)
    path = runtime / "collaborations.jsonl"
    entry = None
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("ticket") == ticket:
                entry = row
    if not entry:
        return {"ticket": ticket, "found": False, "parts": []}

    db = runtime / "company-service.db"
    states: dict[str, str] = {}
    if db.exists():
        try:
            with sqlite3.connect(db) as con:
                for mission, state in con.execute(
                    "select mission_id, status from missions"
                ):
                    states[mission] = state
        except sqlite3.Error:
            pass

    parts = [
        {"department": part["department"], "mission": part["mission"],
         "status": states.get(part["mission"], "yok")}
        for part in entry.get("parts", [])
    ]
    done = sum(1 for part in parts if part["status"] == "completed")
    return {
        "ticket": ticket,
        "found": True,
        "objective": entry.get("objective", ""),
        "parts": parts,
        "completed": done,
        "total": len(parts),
        "progress": round(done / len(parts), 2) if parts else 0.0,
    }
