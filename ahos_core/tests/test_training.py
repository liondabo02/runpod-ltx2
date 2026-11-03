"""Training module tests"""
import json
import sys
sys.path.insert(0, '.')
from pathlib import Path
from ahos.training import build_course, examine

def test_build_course_has_8_questions():
    """build_course should produce 8 questions"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    course = build_course(runtime, 'test-dept')
    assert len(course.questions) == 8, f"Expected 8 questions, got {len(course.questions)}"

def test_build_course_questions_are_tuples():
    """Each question should be a tuple of (question, answer)"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    course = build_course(runtime, 'test-dept')
    for q in course.questions:
        assert isinstance(q, tuple) and len(q) == 2, f"Question should be tuple of 2, got {q}"

def test_examine_returns_score():
    """examine should return a dict with score"""
    course = type('obj', (object,), {'questions': [('q1', 'a1'), ('q2', 'a2')]})()
    result = examine(course, 'worker-01')
    assert 'score' in result
    assert 'passed' in result

def test_training_report_has_departments_workers():
    """training-report.json should have required fields"""
    report_path = Path('/workspace/ahos/ahos_core/config/training-report.json')
    if report_path.exists():
        d = json.loads(report_path.read_text(encoding='utf-8'))
        assert 'departments' in d
        assert 'workers' in d
        assert 'passed' in d
        assert 'failed' in d
        assert 'average_score' in d
