"""Worker mind module tests"""
import sys
from pathlib import Path

sys.path.insert(0, '/workspace/ahos/ahos_core')

from ahos.worker_mind import emotion

def test_emotion_high_barrier():
    """test 1: failures > delivered => stres (> 0.5)"""
    mind = {}
    ctx = {"pending": 0, "delivered": 2, "failures": 5, "quality_rate": 0.5}
    result = emotion(mind, ctx)
    assert result['mood'] == "stres"

def test_emotion_low_barrier():
    """test 2: failures <= delivered => motive"""
    mind = {}
    ctx = {"pending": 0, "delivered": 5, "failures": 2, "quality_rate": 0.8}
    result = emotion(mind, ctx)
    assert result['mood'] == "motive"

def test_emotion_mind_updated():
    """test 3: mind dict mood kaydedildi"""
    mind = {"worker_id": "w1"}
    ctx = {"pending": 0, "delivered": 1, "failures": 1, "quality_rate": 0.5}
    result = emotion(mind, ctx)
    assert 'mood' in result
    assert result['mood'] == "motive"
