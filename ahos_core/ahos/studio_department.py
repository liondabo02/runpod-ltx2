"""Native Office production contracts. No model calls, installs or fake renders."""
from __future__ import annotations
import hashlib
import json
import os
import re
import shutil
import subprocess
import wave
import unicodedata
from dataclasses import dataclass
from pathlib import Path

STAGES = (
    ('brief', 'studio-production-manager-01', (), 'Üretim özeti ve karakter sürekliliği', ('brief.json',)),
    ('story', 'studio-story-director-01', ('brief',), 'Senaryo, sahneler ve diyaloglar', ('story.json',)),
    ('art', 'studio-art-director-01', ('story',), 'Karakter ve mekân görselleri', ('art.json',)),
    ('shots', 'studio-animation-director-01', ('art',), 'Çekim planı ve hareket tasarımı', ('shots.json',)),
    ('voice', 'studio-voice-director-01', ('story',), 'Karakterlere uygun seslendirme', ('voices.json',)),
    ('animation', 'studio-animation-director-01', ('shots',), 'Görsel sahnelerden gerçek animasyon', ('animation.mp4',)),
    ('mix', 'studio-voice-director-01', ('voice', 'animation'), 'Diyalog, müzik ve efekt miksajı', ('mix.wav',)),
    ('assembly', 'studio-production-manager-01', ('animation', 'mix'), 'Görüntü ve ses montajı', ('episode.mp4',)),
    ('qa', 'studio-qa-lead-01', ('assembly',), 'Bağımsız dil, süreklilik ve yaratıcı kalite incelemesi', ('review.json',)),
)

def fold(text):
    value=text.casefold().translate(str.maketrans('ışğüöç','isguoc'))
    return ''.join(c for c in unicodedata.normalize('NFKD',value) if not unicodedata.combining(c))

def matches(text, department=''):
    s=fold(text+' '+department)
    return any(x in s for x in ('cizgi film','animasyon','animation studio','cartoon','film studyosu'))

def language(text):
    s=fold(text)
    named=[code for code,terms in [('en',('ingilizce','english')),('ku',('kurmanci','kurmanji','kurtce')),('tr',('turkce','turkish'))] if any(t in s for t in terms)]
    return named[0] if len(named)==1 else 'tr'

def tasks(text):
    lang=language(text)
    result=[]
    for kind,worker,deps,title,files in STAGES:
        result.append(dict(task_id='studio-'+kind,stage=kind,workflow='studio-production-v1',
            title=f'Çizgi film stüdyosu — {title}. Hedef: {text[:1000]}. Teslim dili={lang}. '
                  f'Çıktılar: {", ".join(files)}. Gerçek üretim sağlayıcısı yoksa engeli kaydet; '
                  'şablon, yazı kartı veya dosya sayısını tamamlanmış üretim sayma.',
            status='pending',worker_id=worker,depends_on=['studio-'+d for d in deps],language=lang,
            expected_artifacts=list(files),attempts=0,max_attempts=2))
    return result

def ready(task, all_tasks):
    states={t['task_id']:t.get('status') for t in all_tasks}
    return task.get('status')=='pending' and task.get('attempts',0)<task.get('max_attempts',2) and all(states.get(d)=='done' for d in task.get('depends_on',[]))

def story_issues(packet, target='tr'):
    issues=[]
    if packet.get('primary_language')!=target:issues.append('Senaryo dili hedef dille eşleşmiyor')
    scenes=packet.get('scenes',[])
    if not isinstance(scenes,list) or not scenes or len(scenes)>100:return issues+['Geçerli sahne listesi yok']
    cast=packet.get('cast_ids',[])
    exposed=[packet.get('title',''),packet.get('logline','')]
    duration=0; ids=set()
    for scene in scenes:
        if not isinstance(scene,dict):issues.append('Geçersiz sahne');continue
        sid=scene.get('scene_id')
        if not sid or sid in ids:issues.append('Sahne kimliği eksik veya yinelenmiş')
        ids.add(sid)
        seconds=scene.get('duration_seconds')
        if type(seconds) not in (int,float) or not 0<seconds<=1200:issues.append('Geçersiz sahne süresi')
        else:duration+=seconds
        exposed.extend(scene.get(k,'') for k in ('title','setting','objective','action_summary'))
        dialogue=scene.get('dialogue')
        if not isinstance(dialogue,list) or not dialogue:issues.append('Diyalog yok');continue
        for line in dialogue:
            if not isinstance(line,dict):issues.append('Geçersiz diyalog');continue
            if line.get('speaker_character_id') not in cast:issues.append('Kanon dışında konuşmacı')
            if not isinstance(line.get('text'),str) or not line['text'].strip():issues.append('Boş diyalog')
            exposed.append(line.get('text',''))
    if packet.get('target_duration_seconds')!=duration:issues.append('Sahne süreleri hedef süreyle eşleşmiyor')
    if target=='tr':
        # Conservative screen for known mixed-language drafts, NOT fluency proof.
        english=re.compile(r'\b(the|with|learns|discovers|his|her|brother|sister|says|scene|children|together|let\x27s)\b',re.I)
        if any(not isinstance(t,str) or english.search(t) for t in exposed):issues.append('Görünür metinde yabancı dil şüphesi; dil incelemesi gerekli')
    return list(dict.fromkeys(issues))

def _json(path):
    if path.stat().st_size>1024*1024:raise ValueError('Belge boyutu sınırı')
    return json.loads(path.read_text(encoding='utf-8-sig'))

def _media(path, audio=False):
    tool=shutil.which('ffprobe')
    if not tool:raise ValueError('Bağımsız ffprobe medya doğrulayıcısı bağlı değil')
    p=subprocess.run([tool,'-v','error','-count_frames','-show_entries','stream=codec_type,codec_name,width,height,nb_read_frames:format=duration','-of','json',str(path)],
                     capture_output=True,timeout=20)
    if p.returncode or len(p.stdout)>256*1024:raise ValueError('Medya okunamıyor')
    body=json.loads(p.stdout);streams=body.get('streams',[])
    if float(body.get('format',{}).get('duration',0))<=0:raise ValueError('Medya süresi yok')
    kinds={x.get('codec_type') for x in streams}
    if ('audio' if audio else 'video') not in kinds:raise ValueError('Beklenen medya akışı yok')
    return body

def acceptance(runtime, idea_id, task, *, owner_review=None):
    """Check actual deliverables. A generic routed/code response cannot finish media."""
    if not re.fullmatch('[0-9a-f]{12}',idea_id):return ['Geçersiz fikir kimliği']
    stage=task.get('stage')
    if stage not in {s[0] for s in STAGES}:return ['Bilinmeyen üretim aşaması']
    root=(Path(runtime)/'studio-production'/idea_id).resolve()
    try:
        folder=(root/stage).resolve()
        if not folder.is_relative_to(root):raise ValueError('Çıktı kapsam dışında')
        receipt=_json(folder/'manifest.json')
        if receipt.get('language')!=task['language']:raise ValueError('Çıktının dili hedefle eşleşmiyor')
        if receipt.get('paid_usd')!=0:raise ValueError('Ücretsiz üretim bütçesi doğrulanmadı')
        files=receipt.get('files')
        if not isinstance(files,dict):raise ValueError('Çıktı manifesti yok')
        paths={}
        for name,sha in files.items():
            path=(folder/name).resolve()
            if not path.is_relative_to(folder) or not path.is_file():raise ValueError('Çıktı eksik veya kapsam dışında')
            if path.stat().st_size>256*1024*1024:raise ValueError('Çıktı boyutu sınırı')
            with path.open('rb') as handle:
                if hashlib.file_digest(handle,'sha256').hexdigest()!=sha:raise ValueError('Çıktı özeti değişti')
            paths[name]=path
        if not set(task['expected_artifacts'])<=paths.keys():raise ValueError('Zorunlu üretim çıktısı eksik')
        if stage=='brief':
            brief=_json(paths['brief.json'])
            if not brief.get('goal') or not brief.get('cast_ids') or brief.get('language')!=task['language']:
                raise ValueError('Üretim amacı, karakter kadrosu veya dil sözleşmesi eksik')
        if stage=='story':return story_issues(_json(paths['story.json']),task['language'])
        if stage=='art':
            art=_json(paths['art.json'])
            images=art.get('images',[])
            if not images:raise ValueError('Karakter ve mekân görselleri üretilmedi')
            for name in images:
                path=paths.get(name)
                if path is None:raise ValueError('Görsel dosyası yok')
                with path.open('rb') as handle:
                    header=handle.read(33);handle.seek(-12,2);ending=handle.read(12)
                if len(header)!=33 or header[:8]!=b'\x89PNG\r\n\x1a\n' or header[12:16]!=b'IHDR' or ending[4:8]!=b'IEND':raise ValueError('Doğrulanabilir PNG görseli yok')
                if int.from_bytes(header[16:20],'big')<256 or int.from_bytes(header[20:24],'big')<256:raise ValueError('Görsel çözünürlüğü yetersiz')
        if stage=='voice':
            voices=_json(paths['voices.json']).get('voices',[])
            if not voices:raise ValueError('Seslendirme kayıtları yok')
            for v in voices:
                if v.get('language')!=task['language'] or not v.get('character_id'):raise ValueError('Ses dili veya karakter eşleşmesi eksik')
                path=paths.get(v.get('file'))
                if path is None:raise ValueError('Ses dosyası yok')
                with wave.open(str(path),'rb') as wav:
                    if wav.getnframes()<wav.getframerate()//10:raise ValueError('Ses kaydı çok kısa')
                    raw=wav.readframes(wav.getnframes())
                    if len(set(raw))<2:raise ValueError('Boş/sessiz ses kaydı')
        if stage in ('animation','assembly'):
            if receipt.get('production_kind')!='animated_scenes':raise ValueError('Yazı kartları animasyon teslimi değildir')
            media=_media(paths['animation.mp4' if stage=='animation' else 'episode.mp4'])
            kinds={s.get('codec_type') for s in media['streams']}
            story=_json(root/'story/story.json')
            if abs(float(media['format']['duration'])-story['target_duration_seconds'])>.5:raise ValueError('Animasyon süresi senaryo süresiyle eşleşmiyor')
            if not any(s.get('codec_type')=='video' and int(s.get('width',0))>=640 and int(s.get('height',0))>=360 and int(s.get('nb_read_frames',0))>1 for s in media['streams']):raise ValueError('Gerçek hareketli görüntü akışı doğrulanmadı')
            if stage=='assembly' and 'audio' not in kinds:raise ValueError('Bölümde seslendirme akışı yok')
        if stage=='mix':_media(paths['mix.wav'],audio=True)
        if stage=='shots':
            shots=_json(paths['shots.json']).get('shots',[])
            if not shots or any(not s.get('action') or not s.get('visual_asset') for s in shots):raise ValueError('Görsel ve hareketli çekim planı eksik')
        if stage=='qa':
            review=_json(paths['review.json'])
            if any(review.get(k) is not True for k in ('language_reviewed','continuity_reviewed','visual_reviewed','voice_reviewed','owner_approved')):
                raise ValueError('İnsan yaratıcı kalite/dil/ses onayı henüz kaydedilmedi')
            # Worker-authored booleans are never proof of a human decision.
            if owner_review is None:
                from .studio_review import approval_matches
                owner_review=lambda ident,receipt:approval_matches(runtime,ident)
            if owner_review(idea_id,receipt) is not True:
                raise ValueError('Bağımsız sahip onay bağlantısı yok; işçi kendi yaratıcı incelemesini onaylayamaz')
        return []
    except (OSError,ValueError,TypeError,KeyError,subprocess.SubprocessError,wave.Error) as exc:
        return [str(exc)[:240]]


# --- Sağlayıcı kaydı (S1) ---------------------------------------------------
# Model adı, fiyat veya vendor adı koda gömülmez: hepsi katalog dosyasından
# (varsayılan `studio/pipeline/providers.json`) okunur. Ücretli sağlayıcı yalnızca
# açık sahip onayı + bütçe kapısıyla seçilebilir; aksi halde ücretsiz yol kalır.


class ProviderRegistryError(ValueError):
    """Katalog geçersiz (şema ihlali, çift kimlik, eksik alan)."""


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    """Tek sağlayıcı kaydı; `adapter` çalıştırma kodunu, `model_ref` config'i işaret eder."""

    provider_id: str
    adapter: str
    task_types: frozenset[str]
    languages: frozenset[str]
    paid: bool
    external: bool
    commercial_default: bool
    priority: int
    model_ref: str = ""

    def supports(self, task_type: str, language: str) -> bool:
        return task_type in self.task_types and language in self.languages

    def to_payload(self) -> dict:
        return {
            "provider_id": self.provider_id,
            "adapter": self.adapter,
            "task_types": sorted(self.task_types),
            "languages": sorted(self.languages),
            "paid": self.paid,
            "external": self.external,
            "commercial_default": self.commercial_default,
            "priority": int(self.priority),
            "model_ref": self.model_ref,
        }


CATALOG_ENV = "AHOS_PROVIDER_CATALOG"
_REQUIRED_FIELDS = ("provider_id", "adapter", "task_types", "languages", "paid",
                    "external", "commercial_default", "priority")


def provider_catalog_path() -> Path:
    """Katalog yolu: ortam değişkeni ya da repo kökündeki varsayılan dosya."""

    override = os.environ.get(CATALOG_ENV, "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "studio" / "pipeline" / "providers.json"


@dataclass(frozen=True, slots=True)
class ProviderRegistry:
    """Katalogdan yüklenen sağlayıcı kaydı; seçim deterministik ve fail-closed."""

    providers: tuple[ProviderDescriptor, ...]

    @classmethod
    def from_payload(cls, payload: dict) -> "ProviderRegistry":
        if not isinstance(payload, dict) or not isinstance(payload.get("providers"), list):
            raise ProviderRegistryError("katalog 'providers' listesi içermeli")
        seen: set[str] = set()
        rows: list[ProviderDescriptor] = []
        for index, item in enumerate(payload["providers"]):
            if not isinstance(item, dict):
                raise ProviderRegistryError(f"providers[{index}] nesne olmalı")
            missing = [field for field in _REQUIRED_FIELDS if field not in item]
            if missing:
                raise ProviderRegistryError(f"providers[{index}] eksik alan: {missing}")
            provider_id = str(item["provider_id"]).strip()
            if not provider_id:
                raise ProviderRegistryError(f"providers[{index}] boş provider_id")
            if provider_id in seen:
                raise ProviderRegistryError(f"çift provider_id: {provider_id}")
            seen.add(provider_id)
            task_types = frozenset(str(value) for value in item["task_types"])
            languages = frozenset(str(value) for value in item["languages"])
            if not task_types or not languages:
                raise ProviderRegistryError(f"{provider_id}: task_types/languages boş olamaz")
            rows.append(ProviderDescriptor(
                provider_id=provider_id,
                adapter=str(item["adapter"]),
                task_types=task_types,
                languages=languages,
                paid=bool(item["paid"]),
                external=bool(item["external"]),
                commercial_default=bool(item["commercial_default"]),
                priority=int(item["priority"]),
                model_ref=str(item.get("model_ref") or ""),
            ))
        if not rows:
            raise ProviderRegistryError("katalog boş")
        return cls(providers=tuple(rows))

    @classmethod
    def load(cls, path: str | Path | None = None) -> "ProviderRegistry":
        source = Path(path) if path else provider_catalog_path()
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProviderRegistryError(f"katalog okunamadı ({source}): {exc}") from exc
        return cls.from_payload(payload)

    def candidates(self, task_type: str, language: str) -> list[ProviderDescriptor]:
        """Uygun sağlayıcılar: ücretsiz → ticari varsayılan → öncelik → kimlik."""

        rows = [row for row in self.providers if row.supports(task_type, language)]
        return sorted(rows, key=lambda row: (row.paid, not row.commercial_default,
                                             int(row.priority), row.provider_id))

    def resolve(self, task_type: str, language: str, *, allow_paid: bool = False,
                approval: str | None = None) -> ProviderDescriptor | None:
        """İlk uygun sağlayıcı; ücretli olan yalnızca onay+bütçe izniyle döner."""

        for row in self.candidates(task_type, language):
            if row.paid:
                if not allow_paid or not str(approval or "").strip():
                    continue
            return row
        return None



# --- Stage-gated acceptance ------------------------------------------------
# Kural: evidence dosyası olmadan stage PASS olamaz; başarısız stage downstream'i
# bloklar. Kısmi "delivery" üretilmez (fail-closed).

STAGE_EVIDENCE: dict[str, tuple[str, ...]] = {    "brief": ("brief.json",),
    "story": ("story.json",),
    "voice": ("voices.json",),
    "animation": ("animation.mp4",),
    "mix": ("mix.wav",),
    "assembly": ("episode.mp4",),
    "qa": ("acceptance.json",),
}

#: Birincil kanıt dosyası yoksa kabul edilecek alternatifler (üretim çıktısı
#: bazı aşamalarda dosya yerine dizin üretir: `voice/`, `animation/`).
EVIDENCE_ALTERNATIVES: dict[str, tuple[str, ...]] = {
    "voices.json": ("voice",),
    "animation.mp4": ("animation",),
}


def require_evidence(stage: str, out_dir, *, evidence: dict | None = None) -> dict:
    """Stage'in zorunlu kanıt dosyalarını doğrular (boş dosya kanıt sayılmaz)."""

    root = Path(out_dir)
    required = tuple((evidence or STAGE_EVIDENCE).get(str(stage), ()))
    missing: list[str] = []
    present: list[str] = []
    for name in required:
        candidate = root / name
        if candidate.is_file() and candidate.stat().st_size > 0:
            present.append(name)
            continue
        alternative = next((root / alt for alt in EVIDENCE_ALTERNATIVES.get(name, ())
                            if ((root / alt).is_file() and (root / alt).stat().st_size > 0)
                            or ((root / alt).is_dir() and any((root / alt).iterdir()))), None)
        if alternative is not None:
            # Dizin/alternatif dosya da kanıttır (ör. `voice/` altındaki replikler).
            present.append(name)
        else:
            missing.append(name)
    return {"stage": str(stage), "required": list(required), "present": present,
            "missing": missing, "ok": not missing}


def stage_gate(out_dir, *, stages=None, evidence: dict | None = None) -> dict:
    """Tüm aşamaları sırayla denetler; ilk başarısız aşamadan sonrası `blocked`."""

    root = Path(out_dir)
    order = tuple(stages or STAGE_EVIDENCE.keys())
    results: list[dict] = []
    blocked: list[str] = []
    blocked_at: str | None = None
    for stage in order:
        if blocked_at is not None:
            blocked.append(stage)
            results.append({"stage": stage, "ok": False, "blocked": True,
                            "missing": [], "reason": f"blocked_by:{blocked_at}"})
            continue
        outcome = require_evidence(stage, root, evidence=evidence)
        results.append(outcome)
        if not outcome["ok"]:
            blocked_at = stage
    return {"root": str(root), "stages": results, "blocked": blocked,
            "blocked_at": blocked_at,
            "ready": blocked_at is None,
            "passed": blocked_at is None}

