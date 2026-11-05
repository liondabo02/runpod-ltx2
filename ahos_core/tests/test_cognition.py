"""Cognition module tests"""
import json
import sys
from pathlib import Path

sys.path.insert(0, '/workspace/ahos/ahos_core')

from ahos.cognition import simulate, plan_from_goal

def test_simulate_with_expected_result():
    """test 1: adımın beklenen sonucu ile eşleştiği durum"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    goal = "test goal"
    steps = [
        {"action": "action1", "expected_result": "result1"},
        {"action": "action2", "expected_result": "result2"},
    ]
    result = simulate(goal, steps)
    
    assert len(result['steps']) == 2
    assert result['steps'][0]['status'] in ('geçti', 'geçti (kısmi)')
    assert result['steps'][1]['status'] in ('geçti', 'geçti (kısmi)')
    assert result['goal'] == goal

def test_simulate_partial_match():
    """test 2: kısmi eşleşme durumu"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    goal = "test goal 2"
    steps = [
        {"action": "action1", "expected_result": "result1"},
    ]
    result = simulate(goal, steps)
    
    assert len(result['steps']) == 1
    # Kısmi eşleşme durumu olmalı
    assert result['steps'][0]['status'] in ('geçti', 'geçti (kısmi)')

def test_plan_from_goal():
    """test 3: hedefden plan oluşturma"""
    goal = "test goal"
    plan = plan_from_goal(goal)
    
    assert len(plan) == 3
    assert plan[0]['action'].startswith('analyze')
    assert plan[1]['action'].startswith('plan')
    assert plan[2]['action'].startswith('execute')
