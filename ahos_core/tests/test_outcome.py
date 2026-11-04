"""Outcome module tests"""
import json
import sys
from pathlib import Path

sys.path.insert(0, '/workspace/ahos/ahos_core')

from ahos.outcome import record, adjust

def test_record_writes_jsonl_and_returns_rate():
    """test 1: record jsonl'a yazar ve success_rate hesaplar"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    
    # Önceki kayıtları temizle
    log_path = runtime / 'outcome.jsonl'
    log_path.unlink(missing_ok=True)
    
    # Kayıt yap
    result = record(runtime, 'oyun', True, 12.5)
    
    # JSONL dosyası oluşturuldu mu?
    assert log_path.exists(), 'outcome.jsonl should exist'
    
    # Tek satır var mı?
    entries = json.loads(log_path.read_text())
    assert len(entries) == 1
    assert entries[0]['department'] == 'oyun'
    assert entries[0]['ok'] == True
    assert entries[0]['duration_s'] == 12.5
    
    # success_rate ve samples döndü mu?
    assert 'success_rate' in result
    assert 'samples' in result
    assert result['success_rate'] == 1.0
    assert result['samples'] == 1

def test_adjust_narrow_when_failing():
    """test 2: adjust: 3 başarısız kayıt → scope=narrow"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    log_path = runtime / 'outcome.jsonl'
    log_path.unlink(missing_ok=True)
    
    # 3 başarısız kayıt ekle
    for i in range(3):
        record(runtime, 'test-dept', False, float(i+1))
    
    # adjust çağr
    result = adjust(runtime, 'test-dept')
    
    assert result['scope'] == 'narrow', f"Expected narrow, got {result['scope']}"
    assert result['reason'] == 'başarı düşük', f"Expected 'başarı düşük', got {result['reason']}"

def test_adjust_wide_when_succeeding():
    """test 3: adjust: 10 başarılı kayıt → scope=wide"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    log_path = runtime / 'outcome.jsonl'
    log_path.unlink(missing_ok=True)
    
    # 10 başarılı kayıt ekle
    for i in range(10):
        record(runtime, 'test-dept', True, float(i+1))
    
    # adjust çağr
    result = adjust(runtime, 'test-dept')
    
    assert result['scope'] == 'wide', f"Expected wide, got {result['scope']}"
    assert result['reason'] == 'başarı yüksek', f"Expected 'başarı yüksek', got {result['reason']}"

def test_adjust_keep_when_mixed():
    """test 4: boş geçmiş → scope=keep"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    log_path = runtime / 'outcome.jsonl'
    log_path.unlink(missing_ok=True)
    
    # Kayıt yok, adjust çağr
    result = adjust(runtime, 'test-dept')
    
    assert result['scope'] == 'keep', f"Expected keep, got {result['scope']}"
    assert result['reason'] == 'veri yok', f"Expected 'veri yok', got {result['reason']}"
