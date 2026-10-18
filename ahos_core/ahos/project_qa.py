"""Independent bounded static web acceptance; no model or project code execution."""
import hashlib
import json
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


def make_project_qa(project_root, evidence_root):
    root = Path(project_root).resolve()
    evidence = Path(evidence_root).resolve()

    def verify(item, result, qa_worker_id):
        from . import mission_guard

        mission_guard.guard()
        problems = []
        hashes = {}
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
            if item.task_id.rsplit(':', 1)[-1] != 'brief':
                index = detect_web_root(root) / 'index.html'
                # Statik web denetimi yalnız web projelerine uygulanır; web
                # olmayan projelerde bütünlük + kanıt kontrolleri yeterlidir.
                if index.is_file():
                    report = scan_assets(root)
                    if not report.checked_files or report.missing:
                        raise ValueError('Bağımsız varlık denetimi başarısız')
                    gate = root / 'tools' / 'check_offline.py'
                    if gate.is_file():
                        from .acceptance import trusted_gate

                        trusted, reason, _digest = trusted_gate(
                            root, evidence / 'acceptance-baseline.json'
                        )
                        if not trusted:
                            raise ValueError('Kabul testi güvenilir değil: ' + reason)
                        acceptance = subprocess.run(
                            [sys.executable, str(gate)],
                            capture_output=True,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            timeout=120,
                            cwd=str(root),
                        )
                        if acceptance.returncode != 0:
                            detail = (acceptance.stdout or acceptance.stderr or '').strip()
                            raise ValueError(
                                'Kabul testi başarısız (check_offline): '
                                + detail.splitlines()[-1][:160]
                            )
            # Fence changes occurring between inventory and acceptance.
            for name, digest in hashes.items():
                if digest_file(root / name, MAX_PROJECT_BYTES)[0] != digest:
                    raise ValueError('Dosya bağımsız denetim sırasında değişti')
        except (OSError, ValueError) as exc:
            problems.append(str(exc) if isinstance(exc, ValueError) else 'Dosya okunamadı')
        passed = not problems
        record = dict(task_id=item.task_id, producer=result.worker_id, verifier=qa_worker_id,
                      passed=passed, scope='static web integrity only; functionality and human fit unverified',
                      source_hashes=hashes, problems=problems, model_calls=0)
        evidence.mkdir(parents=True, exist_ok=True)
        safe = re.sub('[^A-Za-z0-9_-]', '_', item.task_id)[:100]
        path = evidence / ('qa-' + safe + '-' + uuid.uuid4().hex + '.json')
        with path.open('x', encoding='utf-8') as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
        return QaExecutionResult(task_id=item.task_id, qa_worker_id=qa_worker_id, passed=passed,
                                 summary=('Bağımsız statik web denetimi geçti' if passed else '; '.join(problems)) + '; kanıt: ' + str(path))

    return verify
