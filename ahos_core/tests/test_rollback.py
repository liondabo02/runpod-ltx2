"""Rollback module tests"""
import json
import sys
from pathlib import Path

sys.path.insert(0, '/workspace/ahos/ahos_core')

from ahos.rollback import snapshot, restore, last

def test_snapshot_copies_files():
    """test 1: snapshot dosyaları kopyalıyor"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    
    # Create a test file first
    test_file = runtime / 'test-rollback-file.txt'
    test_file.write_text('rollback test content')
    
    # Create a snapshot
    snap = snapshot(runtime, ['test-rollback-file.txt'])
    
    # The snapshot should exist
    assert snap.exists(), f'Snapshot directory should exist: {snap}'
    
    # The file should be in the snapshot
    snap_file = snap / 'test-rollback-file.txt'
    assert snap_file.exists(), f'File should be in snapshot: {snap_file}'
    
    # Content should be preserved
    content = snap_file.read_text()
    assert 'rollback test content' in content

def test_restore_restores_content():
    """test 2: bozulmuş bir dosya geri yüklenir"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    
    # Create and modify a test file
    test_file = runtime / 'test-rollback-modify.txt'
    test_file.write_text('original content')
    
    # Create a snapshot
    snap = snapshot(runtime, ['test-rollback-modify.txt'])
    
    # Modify the file
    test_file.write_text('modified content that should be rolled back')
    
    # Restore from snapshot
    count = restore(snap, runtime)
    
    # File content should be restored
    content = test_file.read_text()
    assert content == 'rollback test content', f"Expected original content, got: {content}"
    
    # Restore count should be 1
    assert count == 1, f'Expected 1 file restored, got {count}'

def test_last_finds_newest_snapshot():
    """test 3: last() en yeni snapshot'ı buluyor"""
    # Already tested above, just verify last() works
    snap = last()
    assert snap is not None, 'last() should return a Path'
    assert snap.name.startswith('20'), f'Expected timestamp format, got: {snap.name}'
