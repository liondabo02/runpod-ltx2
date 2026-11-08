"""Controlled regression repair on the previously isolated real project copy."""
import json
import re
import sys
import time
from pathlib import Path
from ahos.owner_console import build_default_console
from ahos.project_qa import digest_file, MAX_PROJECT_BYTES

folder = Path(sys.argv[1])
index = folder / 'project/www/index.html'
original = index.read_text(encoding='utf-8')
pattern = r'<meta\b[^>]*\bname\s*=\s*["\']viewport["\'][^>]*>'
broken, removed = re.subn(pattern, '', original, flags=re.IGNORECASE)
assert removed > 0, 'Expected existing viewport metadata'
index.write_text(broken, encoding='utf-8')
assert not re.search(pattern, broken, flags=re.IGNORECASE)
console = build_default_console(folder / 'holding')
started = time.monotonic()
result = console.handle('Oyun projesinin web kalite eksiklerini kontrol et ve düzelt')
after = index.read_text(encoding='utf-8')
repaired = re.search(pattern, after, flags=re.IGNORECASE) is not None
reports = [json.loads(p.read_text(encoding='utf-8')) for p in console.artifacts_root.glob('qa-*.json')]
current = [r for r in reports if r['task_id'].startswith(result.mission.mission_id + ':')]
assert repaired and len(current) == 3 and all(r['passed'] for r in current)
assert result.status == 'routed'
record = dict(status='CONTROLLED_REGRESSION_REPAIRED', defect_injected_only_in_isolated_copy=True,
              defect='removed viewport meta', independently_checked_repaired=repaired,
              qa_passed=len(current), mission_id=result.mission.mission_id,
              seconds=round(time.monotonic()-started, 3), model_calls=0,
              ai_generation_verified=False, original_project_modified=False)
(folder / 'repair-delivery.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps(record, indent=2))
