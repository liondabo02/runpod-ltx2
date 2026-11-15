from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping

from .character_memory import CharacterBibleStore


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _hash(value: object) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


class AudioPipelineError(RuntimeError):
    pass


class UnknownSpeakerError(AudioPipelineError):
    pass


class UnsupportedLanguageError(AudioPipelineError):
    pass


class AudioTaskType(str, Enum):
    DIALOGUE_TTS = "dialogue_tts"
    NARRATION_TTS = "narration_tts"
    MUSIC_CUE = "music_cue"
    SFX_CUE = "sfx_cue"
    MIX = "mix"
    LOCALIZATION_QA = "localization_qa"


@dataclass(frozen=True, slots=True)
class LanguagePolicy:
    code: str
    label: str
    required: bool
    human_review_required: bool = True


@dataclass(frozen=True, slots=True)
class VoiceProfile:
    character_id: str
    voice_id: str
    provider_preference: tuple[str, ...]
    speaking_style: str = "age-appropriate, clear, warm"
    reference_audio_uri: str | None = None


@dataclass(frozen=True, slots=True)
class LocalizedDialogue:
    line_id: str
    episode_id: str
    scene_id: str
    speaker_character_id: str
    source_language: str
    target_language: str
    source_text: str
    localized_text: str
    localization_status: str


@dataclass(frozen=True, slots=True)
class AudioJob:
    job_id: str
    task_type: AudioTaskType
    episode_id: str
    scene_id: str
    language: str
    speaker_character_id: str | None
    provider_id: str | None
    payload: dict[str, object]
    paid: bool
    external: bool

    def to_payload(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "task_type": self.task_type.value,
            "episode_id": self.episode_id,
            "scene_id": self.scene_id,
            "language": self.language,
            "speaker_character_id": self.speaker_character_id,
            "provider_id": self.provider_id,
            "payload": self.payload,
            "paid": self.paid,
            "external": self.external,
        }


@dataclass(frozen=True, slots=True)
class AudioProviderDescriptor:
    provider_id: str
    name: str
    supported_languages: frozenset[str]
    capabilities: frozenset[str]
    paid: bool
    external: bool
    commercial_default: bool
    priority: int


class AudioProviderRegistry:
    def __init__(self, providers: Iterable[AudioProviderDescriptor]) -> None:
        self._providers = {provider.provider_id: provider for provider in providers}

    def list(self) -> tuple[AudioProviderDescriptor, ...]:
        return tuple(
            sorted(self._providers.values(), key=lambda p: (p.priority, p.provider_id))
        )

    def choose(
        self,
        *,
        language: str,
        capability: str,
        allow_paid: bool,
        allow_external: bool,
        commercial_use: bool,
        preferred: tuple[str, ...] = (),
    ) -> AudioProviderDescriptor:
        candidates = [
            provider
            for provider in self._providers.values()
            if language in provider.supported_languages
            and capability in provider.capabilities
            and (allow_paid or not provider.paid)
            and (allow_external or not provider.external)
            and (not commercial_use or provider.commercial_default)
        ]

        for preferred_id in preferred:
            for provider in candidates:
                if provider.provider_id == preferred_id:
                    return provider

        if not candidates:
            raise UnsupportedLanguageError(
                f"no allowed provider for language={language!r}, capability={capability!r}"
            )

        return sorted(candidates, key=lambda p: (p.priority, p.provider_id))[0]


def default_audio_provider_registry() -> AudioProviderRegistry:
    return AudioProviderRegistry(
        (
            AudioProviderDescriptor(
                provider_id="runpod-kokoro",
                name="Existing RunPod Kokoro TTS",
                supported_languages=frozenset({"en"}),
                capabilities=frozenset({"tts"}),
                paid=True,
                external=True,
                commercial_default=True,
                priority=30,
            ),
            AudioProviderDescriptor(
                provider_id="chatterbox-multilingual",
                name="Chatterbox Multilingual",
                supported_languages=frozenset(
                    {"tr", "de", "ar", "fr", "es", "en"}
                ),
                capabilities=frozenset({"tts", "voice_cloning"}),
                paid=True,
                external=True,
                commercial_default=True,
                priority=20,
            ),
            AudioProviderDescriptor(
                provider_id="fish-speech-s2",
                name="Fish Speech S2",
                supported_languages=frozenset(
                    {"en", "de", "ar", "fr", "es"}
                ),
                capabilities=frozenset({"tts", "voice_cloning"}),
                paid=True,
                external=True,
                commercial_default=False,
                priority=40,
            ),
            AudioProviderDescriptor(
                provider_id="f5-tts",
                name="F5-TTS",
                supported_languages=frozenset({"en", "de", "ar", "fr", "es"}),
                capabilities=frozenset({"tts", "voice_cloning"}),
                paid=True,
                external=True,
                commercial_default=False,
                priority=50,
            ),
        )
    )


DEFAULT_LANGUAGE_POLICIES = (
    LanguagePolicy("tr", "Turkish", True),
    LanguagePolicy("de", "German", True),
    LanguagePolicy("ar", "Arabic", True),
    LanguagePolicy("fr", "French", True),
    LanguagePolicy("es", "Spanish", True),
    LanguagePolicy("en", "English", True),
    LanguagePolicy("ku", "Kurdish", False),
)


class AudioProductionPlanner:
    def __init__(
        self,
        *,
        character_store: CharacterBibleStore,
        provider_registry: AudioProviderRegistry | None = None,
    ) -> None:
        self.character_store = character_store
        self.providers = provider_registry or default_audio_provider_registry()

    def validate_speaker(self, character_id: str) -> None:
        if self.character_store.get_profile(character_id) is None:
            raise UnknownSpeakerError(character_id)

    def make_localization_stub(
        self,
        *,
        line_id: str,
        episode_id: str,
        scene_id: str,
        speaker_character_id: str,
        source_language: str,
        target_language: str,
        source_text: str,
    ) -> LocalizedDialogue:
        self.validate_speaker(speaker_character_id)
        known = {policy.code for policy in DEFAULT_LANGUAGE_POLICIES}
        if target_language not in known:
            raise UnsupportedLanguageError(target_language)

        # This is intentionally a planning stub, not fake translation.
        localized = source_text if source_language == target_language else ""
        status = "source_ready" if localized else "translation_required"
        return LocalizedDialogue(
            line_id=line_id,
            episode_id=episode_id,
            scene_id=scene_id,
            speaker_character_id=speaker_character_id,
            source_language=source_language,
            target_language=target_language,
            source_text=source_text,
            localized_text=localized,
            localization_status=status,
        )

    def make_tts_job(
        self,
        dialogue: LocalizedDialogue,
        *,
        voice: VoiceProfile,
        allow_paid: bool,
        allow_external: bool,
        commercial_use: bool = True,
    ) -> AudioJob:
        self.validate_speaker(dialogue.speaker_character_id)

        if dialogue.localization_status != "source_ready" and not dialogue.localized_text.strip():
            raise AudioPipelineError(
                f"dialogue {dialogue.line_id} must be localized before TTS"
            )

        provider = self.providers.choose(
            language=dialogue.target_language,
            capability="tts",
            allow_paid=allow_paid,
            allow_external=allow_external,
            commercial_use=commercial_use,
            preferred=voice.provider_preference,
        )

        payload = {
            "text": dialogue.localized_text,
            "voice_id": voice.voice_id,
            "speaking_style": voice.speaking_style,
            "reference_audio_uri": voice.reference_audio_uri,
        }
        return AudioJob(
            job_id=f"tts:{dialogue.episode_id}:{dialogue.line_id}:{dialogue.target_language}",
            task_type=AudioTaskType.DIALOGUE_TTS,
            episode_id=dialogue.episode_id,
            scene_id=dialogue.scene_id,
            language=dialogue.target_language,
            speaker_character_id=dialogue.speaker_character_id,
            provider_id=provider.provider_id,
            payload=payload,
            paid=provider.paid,
            external=provider.external,
        )

    @staticmethod
    def make_music_cue(
        *,
        episode_id: str,
        scene_id: str,
        language: str,
        mood: str,
        duration_seconds: int,
    ) -> AudioJob:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be > 0")
        return AudioJob(
            job_id=f"music:{episode_id}:{scene_id}",
            task_type=AudioTaskType.MUSIC_CUE,
            episode_id=episode_id,
            scene_id=scene_id,
            language=language,
            speaker_character_id=None,
            provider_id=None,
            payload={
                "mood": mood,
                "duration_seconds": duration_seconds,
                "vocals_allowed": False,
                "child_safe_required": True,
            },
            paid=False,
            external=False,
        )


class AudioManifestStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audio_jobs (
                    job_id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    language TEXT NOT NULL,
                    provider_id TEXT,
                    payload_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def upsert_planned(self, job: AudioJob) -> None:
        payload = job.to_payload()
        digest = _hash(payload)
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audio_jobs (
                    job_id, episode_id, task_type, language, provider_id,
                    payload_hash, payload_json, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'planned', ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    provider_id=excluded.provider_id,
                    payload_hash=excluded.payload_hash,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    job.job_id,
                    job.episode_id,
                    job.task_type.value,
                    job.language,
                    job.provider_id,
                    digest,
                    _stable_json(payload),
                    now,
                    now,
                ),
            )

    def count(self, episode_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM audio_jobs WHERE episode_id=?",
                (episode_id,),
            ).fetchone()
        return int(row["c"])


# --- Konuşma profili + sağlayıcı çözümü -------------------------------------
# Profil ve sağlayıcı seçimi config'ten gelir; kodda ses adı/fiyat/model yok.
# Ücretli/dış sağlayıcı yalnızca açık owner-approval + bütçe ile çağrılabilir.

DEFAULT_SPEAKING_PROFILE = {"pitch": "+0Hz", "rate": "+0%",
                            "style_prompt": "clear, warm, age appropriate"}


def speaking_profiles_path() -> Path:
    """Konuşma profili kataloğu (repo kökünde, config)."""

    return Path(__file__).resolve().parents[2] / "studio" / "pipeline" / "speaking_profiles.json"


def load_speaking_profiles(path: str | Path | None = None) -> dict:
    """`role_type` / `age_band` anahtarlı konuşma profillerini yükler."""

    source = Path(path) if path else speaking_profiles_path()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AudioPipelineError(f"profil dosyası okunamadı ({source}): {exc}") from exc
    if not isinstance(payload, dict):
        raise AudioPipelineError(f"profil dosyası nesne olmalı: {source}")
    return payload


def speaking_profile(role_type: str | None = None, age_band: str | None = None,
                     *, profiles: dict | None = None) -> dict:
    """Bilinmeyen rol/yaş için güvenli varsayılana düşer."""

    data = profiles if profiles is not None else load_speaking_profiles()
    result = dict(DEFAULT_SPEAKING_PROFILE, **dict(data.get("default") or {}))
    for key in (str(age_band or "").strip().lower(), str(role_type or "").strip().lower()):
        if not key:
            continue
        overlay = (data.get("profiles") or {}).get(key)
        if isinstance(overlay, dict):
            result.update({k: v for k, v in overlay.items() if v not in (None, "")})
    return result


@dataclass(frozen=True, slots=True)
class AudioBudgetPolicy:
    """Ses aşaması bütçe/onay politikası (varsayılan: ücretsiz dış sağlayıcı serbest,
    ücretli kesinlikle onay + bütçe ister)."""

    allow_paid: bool = False
    allow_external: bool = True
    commercial_use: bool = True
    approval: str | None = None
    budget_remaining_usd: float = 0.0

    @property
    def approved(self) -> bool:
        return bool(self.allow_paid and str(self.approval or "").strip()
                    and float(self.budget_remaining_usd) > 0)


def studio_audio_provider_registry() -> AudioProviderRegistry:
    """Varsayılan kayıt + ücretsiz yerel sağlayıcı (ücretli sessizce seçilmesin)."""

    free = AudioProviderDescriptor(
        provider_id="local-edge",
        name="Local edge TTS",
        supported_languages=frozenset({"tr", "en", "de"}),
        capabilities=frozenset({"tts"}),
        paid=False,
        external=True,
        commercial_default=True,
        priority=5,
    )
    return AudioProviderRegistry((free, *default_audio_provider_registry().list()))


def resolve_provider(task_type: str, language: str, policy: AudioBudgetPolicy, *,
                     registry: AudioProviderRegistry | None = None
                     ) -> AudioProviderDescriptor | None:
    """Politikaya uygun ilk sağlayıcı; uygun yoksa `None` (sessiz ücretli çağrı yok)."""

    chosen = registry or studio_audio_provider_registry()
    capability = "tts" if "tts" in str(task_type).lower() else str(task_type)
    try:
        return chosen.choose(
            language=language,
            capability=capability,
            allow_paid=policy.approved,
            allow_external=bool(policy.allow_external or policy.approved),
            commercial_use=bool(policy.commercial_use),
        )
    except UnsupportedLanguageError:
        return None


def plan_jobs(episode, policy: AudioBudgetPolicy, *, language: str | None = None,
              registry: AudioProviderRegistry | None = None) -> list[AudioJob]:
    """Bölümü ses işlerine ayırır (yalnız planlama; sağlayıcı çağrılmaz)."""

    lang = str(language or getattr(episode, "language", "tr") or "tr")
    provider = resolve_provider("tts", lang, policy, registry=registry)
    if provider is None:
        raise UnsupportedLanguageError(
            f"tts için izinli sağlayıcı yok (language={lang!r}, paid={policy.approved})")

    jobs: list[AudioJob] = []
    for scene in episode.scenes:
        for index, line in enumerate(scene.lines):
            jobs.append(AudioJob(
                job_id=f"tts:{episode.title}:{scene.scene_id}:{index:02d}:{lang}",
                task_type=AudioTaskType.DIALOGUE_TTS,
                episode_id=str(episode.title),
                scene_id=str(scene.scene_id),
                language=lang,
                speaker_character_id=str(line.speaker),
                provider_id=provider.provider_id,
                payload={"text": str(line.text), "seconds": float(line.seconds)},
                paid=provider.paid,
                external=provider.external,
            ))
        jobs.append(AudioJob(
            job_id=f"music:{episode.title}:{scene.scene_id}:{lang}",
            task_type=AudioTaskType.MUSIC_CUE,
            episode_id=str(episode.title),
            scene_id=str(scene.scene_id),
            language=lang,
            speaker_character_id=None,
            provider_id="local-music-bed",
            payload={"seconds": float(scene.duration()), "backdrop": scene.background},
            paid=False,
            external=False,
        ))
    return jobs


def speech_candidates(task_type: str, language: str, policy: AudioBudgetPolicy, *,
                      registry: AudioProviderRegistry | None = None
                      ) -> list[AudioProviderDescriptor]:
    """Fallback zinciri: uygun sağlayıcılar tek yerde, öncelik sırasıyla."""

    chosen = registry or studio_audio_provider_registry()
    capability = "tts" if "tts" in str(task_type).lower() else str(task_type)
    rows = [
        provider for provider in chosen.list()
        if language in provider.supported_languages
        and capability in provider.capabilities
        and (policy.approved or not provider.paid)
        and (policy.allow_external or policy.approved or not provider.external)
        and (not policy.commercial_use or provider.commercial_default)
    ]
    return sorted(rows, key=lambda p: (p.paid, p.priority, p.provider_id))


def synthesize_with_fallback(job: AudioJob, out_path, adapters: dict, *,
                             policy: AudioBudgetPolicy, registry=None,
                             log=None) -> dict:
    """Sıradaki adapter'ı dener; yanlış dil/boş çıktı veren adapter reddedilir."""

    inform = log or (lambda *_: None)
    tried: list[str] = []
    for provider in speech_candidates(job.task_type.value, job.language, policy,
                                      registry=registry):
        adapter = adapters.get(provider.provider_id)
        if adapter is None:
            continue
        tried.append(provider.provider_id)
        try:
            result = dict(adapter(job, out_path) or {})
        except Exception as exc:  # noqa: BLE001 - sıradaki sağlayıcıya geç
            inform(f"[ses] {provider.provider_id} hata: {exc}")
            continue
        produced_language = str(result.get("language") or job.language)
        if produced_language != job.language:
            inform(f"[ses] {provider.provider_id} yanlış dil ({produced_language}) -> atlandı")
            continue
        if not result.get("path"):
            continue
        return {**result, "provider_id": provider.provider_id, "tried": tried}
    raise AudioPipelineError(f"uygun ses üretilemedi (denenen: {tried})")


