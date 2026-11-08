"""Run a real existing project through isolated free deterministic workers."""
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path
from ahos.owner_console import build_default_console
from ahos.projects import ProjectLink
from ahos.project_qa import digest_file, MAX_PROJECT_BYTES


source = Path(sys.argv[1])
destination = Path(sys.argv[2])
destination.mkdir(parents=True, exist_ok=False)
project = destination / 'project'
before = {}
total = 0
started = time.monotonic()
for entries, path in enumerate(source.rglob('*'), 1):
    if entries > 2048:
        raise ValueError('Source scan limit')
    relative = path.relative_to(source)
    if any(part in {'.git', 'node_modules', '.venv', '__pycache__', 'build', 'dist', '.gradle'} for part in relative.parts):
        continue
    if path.is_symlink():
        raise ValueError('Symlink not copied')
    if not path.is_file():
        continue
    total += path.stat().st_size
    if total > MAX_PROJECT_BYTES or len(before) >= 512:
        raise ValueError('Source copy limit')
    digest, size = digest_file(path, MAX_PROJECT_BYTES)
    before[relative.as_posix()] = digest
    target = project / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    assert digest_file(target, size)[0] == digest

console = build_default_console(destination / 'holding')
console.handle('oyun departmanı kur')
console.projects.link(ProjectLink(project_id='mipiluna-isolated', name='Mipiluna isolated acceptance', path=project.resolve(), department_id='oyun', kind='capacitor-html5-game'))
result = console.handle('Oyun projesinin web kalite eksiklerini kontrol et ve düzelt')
changed = [name for name, digest in before.items() if digest_file(project / name, MAX_PROJECT_BYTES)[0] != digest]
created = [p.relative_to(project).as_posix() for p in project.rglob('*') if p.is_file() and p.relative_to(project).as_posix() not in before]
source_unchanged = all(digest_file(source / name, MAX_PROJECT_BYTES)[0] == digest for name, digest in before.items())
restarted = build_default_console(destination / 'holding')
reports = [json.loads(path.read_text(encoding='utf-8')) for path in console.artifacts_root.glob('qa-*.json')]
report = dict(status=result.status, message=result.message, mission_id=result.mission.mission_id if result.mission else None,
              source_files=len(before), source_bytes=total, source_unchanged=source_unchanged,
              changed_paths=changed, created_paths=created, qa_reports=len(reports),
              qa_passed=sum(r['passed'] for r in reports),
              persistent_missions=len(restarted.queue.list()), seconds=round(time.monotonic()-started, 3),
              model_calls=0, production_project_modified=False,
              scope='Existing Mipiluna copy, deterministic web hygiene and static QA; no new AI feature generation')
(destination / 'delivery.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=True, indent=2))
