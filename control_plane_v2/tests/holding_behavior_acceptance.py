"""Behavior probes; temporary state only, no provider calls or live queue writes."""
import json
import sys
from pathlib import Path
from ahos.owner_console import build_default_console
from ahos.code_work import make_project_executor
from ahos.llm_executor import _verify
from ahos.workforce_execution import WorkItem


def run(root):
    root.mkdir(parents=True, exist_ok=False)
    console = build_default_console(root / 'holding')
    result = console.handle('çizgi film departmanı kur')
    story = console.handle('çizgi film için yeni bir bölüm senaryosu yaz')
    outputs = list((root / 'holding/artifacts').rglob('deliverable.md'))
    restarted = build_default_console(root / 'holding')
    project = root / 'web'
    (project / 'www').mkdir(parents=True)
    (project / 'www/index.html').write_text('<html><script src="missing.js"></script></html>', encoding='utf-8')
    item = WorkItem(task_id='accept:review', title='Eksik dosyaları doğrula', department='software', required_capabilities=frozenset({'verification'}))
    reviewed = make_project_executor(project, root / 'web-evidence')(item, 'test-worker')
    empty = root / 'empty'
    empty.mkdir()
    no_test, reason = _verify(empty, '', run_browser=False)
    marker = (root / 'model-command-marker').resolve()
    command = sys.executable + ' -c ' + '__import__("pathlib").Path(' + repr(str(marker)) + ').touch()'
    # Single token Python code, no shell; harmless marker demonstrates model command trust.
    command_result, _ = _verify(empty, command, run_browser=False)
    return {
        'department_created': result.department_id == 'creative',
        'department_persisted': restarted.book.get('creative') is not None,
        'story_status': story.status,
        'story_mission_status': str(story.mission.status) if story.mission else None,
        'markdown_outputs': len(outputs),
        'static_placeholder_outputs': sum('Bu adim deterministik' in p.read_text(encoding='utf-8') for p in outputs),
        'missing_asset_accepted': reviewed.success,
        'no_verifier_accepted': no_test,
        'model_supplied_command_executed': marker.exists(),
        'model_command_accepted': command_result,
        'external_calls': 0,
    }


if __name__ == '__main__':
    result = run(Path(sys.argv[1]))
    Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True, indent=2))
