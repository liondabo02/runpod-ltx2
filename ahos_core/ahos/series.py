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
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .studio_2d import Episode, Line, Scene

BACKGROUNDS = ("day", "sunset", "night")

#: Sezon boyunca dönen mekân havuzu (dizi devamlılığı: her bölüm farklı mekân).
SEASON_SETTINGS: tuple[str, ...] = (
    "Park", "Ev", "Sokak", "Köprü", "Okul", "Pazar", "Sahil", "Orman", "Meydan", "Tepe",
)


def setting_for(episode_number: int, scene_index: int, *, scenes: int = 4) -> str:
    """Bölüme özgü mekân: aynı bölümde tekrar etmez, bölümler arasında değişir.

    Örnek: 1. bölüm → Park, Ev, Sokak, Köprü · 2. bölüm → Okul, Pazar, Sahil, Orman.
    """

    start = (max(1, int(episode_number)) - 1) * max(1, int(scenes))
    return SEASON_SETTINGS[(start + max(0, int(scene_index))) % len(SEASON_SETTINGS)]


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


DEFAULT_LLM_CONFIG = Path(__file__).resolve().parents[2] / "studio" / "pipeline" / "llm.json"


def load_llm_config(path: str | Path | None = None) -> dict:
    """LLM ayarını config dosyasından ve ortam değişkenlerinden çöz.

    Model/sağlayıcı adı kodda tutulmaz; `provider` adapter kimliği, `model_ref`
    ise config işaretçisidir. Anahtar yalnızca ortam değişkeninden okunur.
    """

    target = Path(path) if path else DEFAULT_LLM_CONFIG
    data: dict = {}
    if target.is_file():
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    if not isinstance(data, dict):
        data = {}
    data["provider"] = os.getenv("AHOS_LLM_PROVIDER") or data.get("provider") or "llm"
    try:
        data["budget_usd_cap"] = float(
            os.getenv("AHOS_LLM_BUDGET_USD", data.get("budget_usd_cap", 0.0))
        )
    except (TypeError, ValueError):
        data["budget_usd_cap"] = 0.0
    data["model"] = os.getenv("AHOS_LLM_MODEL") or data.get("model") or ""
    data["base_url"] = os.getenv("AHOS_LLM_BASE_URL") or data.get("base_url") or ""
    return data


def _llm_adapter(prompt: str, cfg: dict) -> str:
    """OpenAI-uyumlu generic HTTP adapter; model ve endpoint config'ten gelir."""

    api_key = os.getenv("AHOS_LLM_API_KEY", "").strip()
    base_url = str(cfg.get("base_url") or "").strip().rstrip("/")
    model = str(cfg.get("model") or "").strip()
    if not api_key or not base_url or not model:
        raise RuntimeError("LLM adapter config eksik (base_url/model/API key)")
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": int(cfg.get("max_tokens", 800)),
        "temperature": 0.4,
    }).encode("utf-8")
    request = urllib.request.Request(
        base_url + "/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    timeout = float(cfg.get("timeout_s", 40))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"LLM çağrısı başarısız: {type(exc).__name__}") from exc
    try:
        return str(payload["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("LLM yanıtı beklenen şemada değil") from exc


def default_script_adapters() -> dict:
    """Mevcut script adapter'ları: provider_id -> callable(prompt, cfg) -> str."""

    return {"llm": _llm_adapter}


def _template_episode(series: SeriesBible, plan: EpisodePlan, *,
                      lines_per_scene: int, line_seconds: float) -> Episode:
    """Mevcut deterministik şablon; LLM yokken/başarısızken fallback."""

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


def _fit_duration(episode: Episode, target_seconds: float) -> Episode:
    """Tüm replikleri ms aritmetiğiyle hedef toplam süreye tam oturt."""

    lines = [line for scene in episode.scenes for line in scene.lines]
    if not lines:
        return episode
    total_ms = max(len(lines), int(round(float(target_seconds) * 1000)))
    values = [max(1, int(round(float(line.seconds) * 1000))) for line in lines]
    delta = total_ms - sum(values)
    values[-1] = max(1, values[-1] + delta)
    # Son replik negatife düşerse eksik/artan ms'i sondan geriye dağıt.
    for index in range(len(values) - 1, -1, -1):
        overflow = sum(values) - total_ms
        if overflow <= 0:
            break
        take = min(values[index] - 1, overflow)
        values[index] -= take
    for line, milliseconds in zip(lines, values):
        line.seconds = milliseconds / 1000.0
    return episode


def _episode_from_llm(raw: str, series: SeriesBible, plan: EpisodePlan) -> Episode:
    """LLM JSON'unu doğrula ve Episode'a çevir; şema dışıysa hata ver."""

    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("scenes"), list):
        raise ValueError("scenes listesi yok")
    scenes_data = data["scenes"]
    if not scenes_data:
        raise ValueError("sahne yok")
    cast = set(series.cast())
    scenes: list[Scene] = []
    line_count = 0
    for index, scene_data in enumerate(scenes_data):
        if not isinstance(scene_data, dict) or not isinstance(scene_data.get("lines"), list):
            raise ValueError("geçersiz sahne")
        lines: list[Line] = []
        for line_data in scene_data["lines"]:
            if not isinstance(line_data, dict):
                raise ValueError("geçersiz replik")
            speaker = str(line_data.get("speaker") or "")
            text = str(line_data.get("text") or "").strip()
            try:
                seconds = float(line_data.get("seconds"))
            except (TypeError, ValueError):
                raise ValueError("geçersiz süre")
            if speaker not in cast or not text or seconds <= 0:
                raise ValueError("konuşmacı/metin/süre geçersiz")
            lines.append(Line(f"s{index + 1}", speaker, text, seconds))
            line_count += 1
        if not lines:
            raise ValueError("boş sahne")
        scenes.append(Scene(
            scene_id=f"s{index + 1}",
            setting=str(scene_data.get("title") or f"Sahne {index + 1}"),
            background=BACKGROUNDS[index % len(BACKGROUNDS)],
            characters=list(series.cast()),
            lines=lines,
        ))
    if line_count < 8:
        raise ValueError("en az 8 replik gerekli")
    return Episode(title=f"{series.title} · B{plan.number}", scenes=scenes,
                   language=series.language)


def _script_prompt(series: SeriesBible, plan: EpisodePlan, target_seconds: float) -> str:
    first, second = series.cast()
    return (
        "Sen bir çocuk animasyonu senaristisin. Yalnızca JSON döndür; açıklama yazma.\n"
        f"Dizi: {series.title}\nÖncül: {series.premise}\nBölüm: {plan.title}\n"
        f"Konu: {plan.logline}\nKadro: {first}, {second}\n"
        f"Hedef toplam süre: {target_seconds:.3f} saniye.\n"
        "Şema: {\"scenes\":[{\"title\":\"...\",\"lines\":["
        "{\"speaker\":\"aden|kaan\",\"text\":\"...\",\"seconds\":2.5}]}]}\n"
        "En az 8 replik, her replikte geçerli konuşmacı ve boş olmayan Türkçe metin."
    )





def build_episode(series: SeriesBible, plan: EpisodePlan, *,
                  lines_per_scene: int = 4, line_seconds: float = 4.0,
                  script_adapter=None, cfg: dict | None = None,
                  target_seconds: float | None = None,
                  approval: bool = False,
                  ledger_path: str | Path | None = None) -> Episode:
    """Bölüm planını senaryoya çevir; LLM varsa onu, yoksa şablonu kullan.

    Ücretli/uzak adapter yalnızca açık `approval` ve pozitif `budget_usd_cap`
    varsa çağrılır. Şema hatasında bir kez retry edilir; yine olmazsa
    deterministik şablona düşülür ve ledger'a failure_class yazılır.
    """

    cfg = dict(cfg or load_llm_config())
    target = float(target_seconds if target_seconds is not None
                   else (series.episode_seconds if script_adapter else 0.0))
    ledger = {
        "script_source": "template",
        "failure_class": None,
        "blocked_budget": False,
        "provider": cfg.get("provider"),
        "model_ref": cfg.get("model_ref"),
        "attempts": 0,
        "target_seconds": target or None,
    }

    if script_adapter is None:
        provider = str(cfg.get("provider") or "llm")
        script_adapter = default_script_adapters().get(provider)

    budget = float(cfg.get("budget_usd_cap") or 0.0)
    if script_adapter is not None and not approval:
        ledger["blocked_budget"] = True
        ledger["failure_class"] = "approval_required"
        script_adapter = None
    elif script_adapter is not None and budget <= 0:
        ledger["blocked_budget"] = True
        ledger["failure_class"] = "budget_exhausted"
        script_adapter = None

    episode = None
    if script_adapter is not None:
        prompt = _script_prompt(series, plan, target or series.episode_seconds)
        for attempt in (1, 2):
            ledger["attempts"] = attempt
            try:
                raw = script_adapter(prompt, cfg)
                episode = _episode_from_llm(raw, series, plan)
                ledger["script_source"] = "llm"
                ledger["failure_class"] = None
                break
            except Exception:  # noqa: BLE001 - geçersiz çıktıda şablona düş
                episode = None
                ledger["failure_class"] = "invalid_output"
        if episode is None:
            ledger["script_source"] = "template"

    if episode is None:
        episode = _template_episode(series, plan, lines_per_scene=lines_per_scene,
                                    line_seconds=line_seconds)

    if target:
        episode = _fit_duration(episode, target)

    episode.script_ledger = ledger
    if ledger_path is not None:
        path = Path(ledger_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    return episode


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
