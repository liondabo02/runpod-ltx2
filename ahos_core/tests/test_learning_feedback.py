"""Learning feedback module tests"""
import json
import sys
from pathlib import Path

sys.path.insert(0, '/workspace/ahos/ahos_core')

from ahos.learning_feedback import weights, top_cards, apply_to_prompt

def test_weights_creates_dict():
    """weights should return a dict with kart IDs"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    cards = [
        {"id": "card-001", "passed": 4, "questions": 5, "last_seen": 0},
        {"id": "card-002", "passed": 2, "questions": 5, "last_seen": 0},
    ]
    w = weights(runtime, cards)
    assert isinstance(w, dict)
    assert "card-001" in w
    assert "card-002" in w
    assert w["card-001"]["wins"] == 4
    assert w["card-001"]["losses"] == 1

def test_top_cards_returns_sorted():
    """top_cards should return cards sorted by weight"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    w = weights(runtime, [
        {"id": "card-A", "passed": 5, "questions": 5, "last_seen": 0},
        {"id": "card-B", "passed": 1, "questions": 5, "last_seen": 0},
        {"id": "card-C", "passed": 3, "questions": 5, "last_seen": 0},
    ])
    top = top_cards(runtime, n=2)
    assert len(top) == 2
    assert top[0]["id"] == "card-A"
    assert top[0]["weight"] > top[1]["weight"]

def test_apply_to_prompt_enriches():
    """apply_to_prompt should add learned lessons to prompt"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    prompt = "Plan: increase production"
    enriched = apply_to_prompt(runtime, prompt)
    assert "### Öğrenilen dersler" in enriched
    assert "Plan: increase production" in enriched

def test_top_cards_empty_when_no_weights():
    """top_cards should return empty list when no weights"""
    runtime = Path('/workspace/ahos/ahos_core/runtime')
    top = top_cards(runtime, n=3)
    assert top == []
