"""Daemon live tests"""
import json
import sys
from pathlib import Path

sys.path.insert(0, '/workspace/ahos/ahos_core')

from ahos.daemon import tick_once

def test_tick_has_initiative_key():
    """test 1: daemon tick sonrası state.infra içinde 'initiative' anahtarı var"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    departments = [{'department_id': 'oyun'}, {'department_id': 'software'}]
    state = tick_once(runtime, departments)
    assert 'initiative' in state, f"Expected 'initiative' in state.infra, got {state.keys()}"
    assert 'outcome' in state, f"Expected 'outcome' in state.infra, got {state.keys()}"

def test_outcome_scope_valid():
    """test 2: state.infra['outcome']['scope'] in {'narrow','wide','keep'}"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    departments = [{'department_id': 'oyun'}, {'department_id': 'software'}]
    state = tick_once(runtime, departments)
    scope = state.get('outcome', {}).get('scope')
    assert scope in {'narrow', 'wide', 'keep'}, f"Expected scope in {{narrow, wide, keep}}, got {scope}"
