"""Initiative module tests"""
import json
import sys
from pathlib import Path

sys.path.insert(0, '/workspace/ahos/ahos_core')

from ahos.initiative import tick, last

def test_tick_creates_goal_when_pending_less_than_8():
    """test 1: kuyruk boşken hedef üretir"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    pending_path = runtime / 'mission-stats.json'
    pending_path.write_text(json.dumps({'pending': 0}))
    
    depts = [{'department_id': 'oyun'}, {'department_id': 'software'}]
    result = tick(runtime, depts)
    
    assert result['created'] == 1, f"Expected created=1, got {result['created']}"
    assert result['department'] is not None, f"Expected department, got {result['department']}"
    assert result['score'] == 0.8, f"Expected score=0.8, got {result['score']}"
    # JSONL dosyasına yazıldı mı?
    log_path = runtime / 'initiative.jsonl'
    assert log_path.exists(), 'initiative.jsonl should exist'
    entry = json.loads(log_path.read_text().splitlines()[-1])
    assert entry['department'] is not None

def test_tick_no_goal_when_pending_ge_8():
    """test 2: kuyruk >= 8 ise hedef üretmez"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    pending_path = runtime / 'mission-stats.json'
    pending_path.write_text(json.dumps({'pending': 10}))
    
    depts = [{'department_id': 'oyun'}, {'department_id': 'software'}]
    result = tick(runtime, depts)
    
    assert result['created'] == 0, f"Expected created=0, got {result['created']}"
    assert result['department'] is None

def test_last_returns_last_entry():
    """test 3: last() son kaydı döndürür"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    log_path = runtime / 'initiative.jsonl'
    
    # Önceki girişimi temizle ve iki yeni ekle
    log_path.unlink(missing_ok=True)
    
    # İlk girişim
    entry1 = {'at': '2026-11-03T10:00:00', 'department': 'oyun', 'goal': 'oyun için iyileştirme', 'score': 0.8}
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(entry1) + '\n')
    
    # İkinci girişim
    entry2 = {'at': '2026-11-03T11:00:00', 'department': 'software', 'goal': 'software için iyileştirme', 'score': 0.8}
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry2) + '\n')
    
    son = last(runtime)
    assert son is not None, 'last() should return a dict'
    assert son['department'] == 'software', f"Expected 'software', got {son['department']}"
    assert son['score'] == 0.8
