"""Dizi yönetimi: sezon planı, bölüm üretimi, süreklilik durumu.

Neden ayrı modül: tek bölüm üretmek kolay, 50 bölümü tutarlı üretmek zor.
Burada "dizi İncil'i" (series bible) veri olarak tutulur:
- karakterler (kimlik, cinsiyet, ses, palet) — görsel tutarlılık kodla garanti
- ton, dünya, hedef yaş, bölüm süresi
- sezon yayı: her bölümün başlığı, özeti ve kapanış kancası (cliffhanger)

Durum `series-state.json` içinde tutulur; bölüm numarası ve süreklilik
(önceki bölümün kancası) sonraki bölüme taşınır.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .studio_2d import Episode, Line, Scene

BACKGROUNDS = ("day", "sunset", "night")


@dataclass
class Character:
    character_id: str
    name: str
    gender: str = "female"   # edge-tts ses seçimi
    role: str = "ana karakter"


@dataclass
class SeriesBible:
    series_id: str
    title: str
    premise: str
    language: str = "tr"
    target_age: str = "4-8"
    episode_seconds: float = 180.0     # hedef bölüm süresi
    characters: list[Character] = field(default_factory=list)

    def cast(self) -> tuple[str, str]:
        ids = [c.character_id for c in self.characters] or ["aden", "kaan"]
        return (ids[0], ids[1] if len(ids) > 1 else ids[0])


@dataclass
class EpisodePlan:
    number: int
    title: str
    logline: str
    cliffhanger: str


ARC_TEMPLATES: list[tuple[str, str, str]] = [
    ("Yeni bir şey keşfedilir", "Kahramanlar alışılmadık bir iz bulur.", "İzin peşinde biri onları izliyor."),
    ("İlk deneme ters gider", "Plan beklenmedik şekilde bozulur.", "Kayıp parça ortaya çıkar."),
    ("Yardım isterler", "Bir dostları devreye girer.", "Yardım eden kişinin sakladığı bir şey var."),
    ("Sır ortaya çıkar", "Eski bir olay gün yüzüne çıkar.", "Sır, en yakınlarını ilgilendiriyor."),
    ("Zor bir seçim", "İki doğru birbirine ters düşer.", "Seçimin bedeli hemen görünür."),
    ("Geri dönüş yok", "Karar verilir ve kapı kapanır.", "Yeni bir kapı aralanır."),
    ("Beklenmedik misafir", "Kimse onu beklemiyordu.", "Misafir bir uyarı getirir."),
    ("Kayıp hatıra", "Bir anı her şeyi değiştirir.", "Hatıranın sahibi bulunur."),
    ("Yol ayrımı", "Ekip ikiye bölünür.", "Her iki yol da aynı yere çıkar."),
    ("Büyük buluşma", "Herkes aynı yerde toplanır.", "Buluşma bir hesaplaşmaya döner."),
]


def plan_season(series: SeriesBible, *, episodes: int = 10) -> list[EpisodePlan]:
    plans: list[EpisodePlan] = []
    for index in range(episodes):
        beat, logline, cliffhanger = ARC_TEMPLATES[index % len(ARC_TEMPLATES)]
        plans.append(EpisodePlan(
            number=index + 1,
            title=f"{beat} · Bölüm {index + 1}",
            logline=logline,
            cliffhanger=cliffhanger,
        ))
    return plans


def build_episode(series: SeriesBible, plan: EpisodePlan, *,
                  lines_per_scene: int = 4, line_seconds: float = 4.0) -> Episode:
    """Bölüm planını sahne sahne senaryoya çevir; karakterler sabittir."""

    first, second = series.cast()
    scenes_per_episode = 4
    scenes: list[Scene] = []
    for index in range(scenes_per_episode):
        background = BACKGROUNDS[index % len(BACKGROUNDS)]
        opening = index == 0
        closing = index == scenes_per_episode - 1
        setting = ("Açılış" if opening else "Kapanış" if closing else f"Sahne {index + 1}")
        lines: list[Line] = []
        for line_index in range(lines_per_scene):
            speaker = first if line_index % 2 == 0 else second
            if opening and line_index == 0:
                text = f"{series.title}: {plan.title}! {plan.logline}"
            elif opening and line_index == 1:
                text = "Hazırsan başlayalım!"
            elif closing and line_index >= lines_per_scene - 2:
                text = plan.cliffhanger if line_index == lines_per_scene - 1 else "Ama bu ne demek?"
            else:
                text = f"{plan.logline}" if line_index % 2 == 0 else "Bu iş göründüğünden zor."
            lines.append(Line(f"s{index + 1}", speaker, text, line_seconds))
        scenes.append(Scene(
            scene_id=f"s{index + 1}", setting=setting, background=background,
            characters=[first, second], lines=lines,
        ))
    return Episode(title=f"{series.title} · B{plan.number}", scenes=scenes,
                   language=series.language)


def state_path(root: str | Path) -> Path:
    return Path(root) / "series-state.json"


def load_state(root: str | Path) -> dict:
    path = state_path(root)
    if not path.is_file():
        return {"produced": [], "next_episode": 1}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(root: str | Path, state: dict) -> Path:
    path = state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def series_manifest(series: SeriesBible) -> dict:
    return asdict(series)
