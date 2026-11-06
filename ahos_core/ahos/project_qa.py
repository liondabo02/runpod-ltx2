"""Bounded integrity/browser checks and owner-pinned functional acceptance.

No model calls. An existing trusted acceptance script runs with a timeout;
production callers require it, while legacy static-only callers are explicit.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from .code_work import scan_assets, detect_web_root, IGNORED_PARTS
from .worker_runtime import QaExecutionResult


MAX_PROJECT_BYTES = 256 * 1024 * 1024
HASH_CHUNK_BYTES = 64 * 1024
MAX_ENTRIES = 20_000
MAX_HASHED_FILES = 4_096

#: Uretim zincirindeki adim sirasi (onceki adimin hash'leri ile karsilastirma icin).
_STEP_ORDER = ('brief', 'produce', 'review')


def _previous_source_hashes(evidence, task_id):
    """Onceki adimin kaynak hash kaydini dondur (yoksa None).

    Amac: "derlendi" ile "teslim edildi" arasindaki farki yakalamak. Uretim
    adimi, onceki adimdan bu yana hicbir dosyayi degistirmediyse bu bir
    teslimat degildir.
    """
    mission, _, step = str(task_id).rpartition(':')
    try:
        index = _STEP_ORDER.index(step)
    except ValueError:
        return None
    if index == 0:
        return None
    previous_step = _STEP_ORDER[index - 1]
    candidates = sorted(Path(evidence).glob(f'qa-{mission}_{previous_step}-*.json'))
    if not candidates:
        return None
    try:
        payload = json.loads(candidates[-1].read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    hashes = payload.get('source_hashes')
    return hashes if isinstance(hashes, dict) else None


def digest_file(path, limit):
    digest = hashlib.sha256()
    read = 0
    with path.open('rb') as stream:
        while True:
            chunk = stream.read(min(HASH_CHUNK_BYTES, limit - read + 1))
            if not chunk:
                break
            read += len(chunk)
            if read > limit:
                raise ValueError('Dosya okuma kaynak sınırı aşıldı')
            digest.update(chunk)
    return digest.hexdigest(), read


def _browser_smoke(index, evidence, task_id):
    """Load the page in a headless browser when one is available.

    A web deliverable must pass real browser checks. No browser means
    unverified delivery, not an automatic QA pass.
    """

    if os.environ.get('AHOS_BROWSER_QA', '1').strip().lower() in {'0', 'false', 'off', 'no'}:
        return None
    try:
        from .browser_check import check_page, find_browser

        if find_browser() is None:
            return {'ok': False, 'problems': 'tarayıcı bulunamadı; web teslimatı doğrulanamadı'}
        safe = re.sub('[^A-Za-z0-9_-]', '_', task_id)[:80]
        check = check_page(index, Path(evidence) / 'browser' / safe)
    except Exception as exc:  # browser check must never crash QA
        return {'ok': False, 'problems': f'{type(exc).__name__}: {exc}'[:200]}
    return {
        'ok': bool(check.ok),
        'dom_bytes': int(check.dom_bytes),
        'seconds': float(check.seconds),
        'problems': '; '.join(check.problems[:2]),
        'screenshot': check.screenshot,
    }


def make_project_qa(project_root, evidence_root, *, require_functional=False):
    root = Path(project_root).resolve()
    evidence = Path(evidence_root).resolve()

    def verify(item, result, qa_worker_id):
        from . import mission_guard

        mission_guard.guard()
        problems = []
        hashes = {}
        browser = None
        functional_verified = False
        try:
            if result.task_id != item.task_id or not result.success:
                raise ValueError('İşçi sonucu görevle eşleşmiyor veya başarısız')
            if qa_worker_id == result.worker_id:
                raise ValueError('Üreten işçi kendi çıktısını onaylayamaz')
            total = 0
            for entries, path in enumerate(root.rglob('*'), 1):
                if entries > MAX_ENTRIES:
                    raise ValueError('Bağımsız denetim tarama sınırı aşıldı')
                if any(part in IGNORED_PARTS for part in path.relative_to(root).parts):
                    continue
                if path.is_symlink() or not path.resolve().is_relative_to(root):
                    raise ValueError('Proje dışına bağlantı reddedildi')
                if not path.is_file():
                    continue
                size = path.stat().st_size
                total += size
                if len(hashes) >= MAX_HASHED_FILES or total > MAX_PROJECT_BYTES:
                    raise ValueError('Bağımsız denetim kaynak sınırı aşıldı')
                digest, read = digest_file(path, size)
                if read != size:
                    raise ValueError('Dosya denetim sırasında değişti')
                hashes[path.relative_to(root).as_posix()] = digest
            for artifact in result.artifacts:
                path = Path(artifact).resolve()
                if not path.is_relative_to(evidence) or not path.is_file():
                    raise ValueError('İşçi kanıtı yok veya izinli kanıt alanı dışında')
            if not result.artifacts:
                raise ValueError('İşçi kanıt dosyası sunmadı')
            step_name = item.task_id.rsplit(':', 1)[-1]
            productive_required = os.environ.get(
                'AHOS_REQUIRE_PRODUCTIVE_CHANGE', '0'
            ).strip().lower() in {'1', 'true', 'yes', 'on'}
            if step_name == 'produce' and productive_required:
                # "Derleniyor" tek basina teslim kaniti degildir: uretim adimi
                # gercekten bir dosya degistirmis olmali. Uretimde daemon bu
                # politikayi acar (AHOS_REQUIRE_PRODUCTIVE_CHANGE=1).
                # Inceleme/dogrulama adimlari projeyi degistirmez; onlarin isi
                # zaten mevcut hali denetlemektir, bu yuzden kural onlara uygulanmaz.
                previous = _previous_source_hashes(evidence, item.task_id)
                if previous is not None and previous == hashes:
                    raise ValueError(
                        'Üretim adımı hiçbir dosyayı değiştirmedi (no_change): '
                        'teslimat yok, yalnızca mevcut hâl doğrulandı'
                    )
            if item.task_id.rsplit(':', 1)[-1] != 'brief':
                index = detect_web_root(root) / 'index.html'
                # Statik web denetimi yalnız web projelerine uygulanır; web
                # olmayan projelerde bütünlük + kanıt kontrolleri yeterlidir.
                if index.is_file():
                    report = scan_assets(root)
                    if not report.checked_files or report.missing:
                        raise ValueError('Bağımsız varlık denetimi başarısız')
                    browser = _browser_smoke(index, evidence, item.task_id)
                    if browser is not None and not browser.get('ok'):
                        raise ValueError(
                            'Tarayıcı duman testi başarısız: '
                            + str(browser.get('problems') or 'sayfa yüklenemedi')
                        )
                gate = root / 'tools' / 'check_offline.py'
                if require_functional and not gate.is_file():
                    raise ValueError('Bağımsız işlevsel kabul testi yok; ürün tamamlandı sayılamaz')
                if gate.is_file():
                    from .acceptance import trusted_gate

                    trusted, reason, _digest = trusted_gate(
                        root, evidence / 'acceptance-baseline.json'
                    )
                    if not trusted:
                        raise ValueError('Kabul testi güvenilir değil: ' + reason)
                    # Trust is pinned separately; execute the project's own
                    # pytest suite instead of candidate-controlled gate code.
                    from .acceptance import check_offline

                    ok, detail = check_offline(root, python=sys.executable)
                    if not ok:
                        raise ValueError(
                            'Kabul testi başarısız (check_offline): ' + detail
                        )
                functional_verified = gate.is_file()
            # Fence changes occurring between inventory and acceptance.
            for name, digest in hashes.items():
                if digest_file(root / name, MAX_PROJECT_BYTES)[0] != digest:
                    raise ValueError('Dosya bağımsız denetim sırasında değişti')
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            problems.append('Kabul testi zaman aşımı' if isinstance(exc, subprocess.TimeoutExpired)
                            else str(exc) if isinstance(exc, ValueError) else 'Dosya okunamadı')
        passed = not problems
        record = dict(task_id=item.task_id, producer=result.worker_id, verifier=qa_worker_id,
                      passed=passed, scope='file integrity + headless DOM smoke for web when enabled; functionality and human fit unverified',
                      source_hashes=hashes, problems=problems, model_calls=0,
                      functional_required=require_functional, functional_verified=functional_verified,
                      browser=browser)
        evidence.mkdir(parents=True, exist_ok=True)
        safe = re.sub('[^A-Za-z0-9_-]', '_', item.task_id)[:100]
        path = evidence / ('qa-' + safe + '-' + uuid.uuid4().hex + '.json')
        with path.open('x', encoding='utf-8') as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
        return QaExecutionResult(task_id=item.task_id, qa_worker_id=qa_worker_id, passed=passed,
                                 summary=('Bağımsız statik web denetimi geçti' if passed else '; '.join(problems)) + '; kanıt: ' + str(path))

    return verify
