# -*- coding: utf-8 -*-
"""AHOS duygu motoru: replik ve eylem metninden karakterin yüz ifadesini seçer (kaş, göz kapağı, ağız).
Çıktı: angry | sad | sly | laugh | surprise | curious | happy | neutral. Kural tabanlı, deterministik, LLM gerekmez."""
import re

RULES = [
    ("angry", r"kız(dı|gın|ar)|öfke|bağır|yeter|dur!|sinir|hayır!|olmaz!"),
    ("sad", r"üzül|ağla|hüzün|yazık|maalesef|kırıl|özle|yalnız|korku|korktu"),
    ("surprise", r"şaşır|vay|aman|inanamıyorum|nasıl|gerçekten mi|aniden|birden|irkil|\b[Aa]a+\s*!|\beyvah"),
    ("sly", r"kurnaz|sırıt|şaka|hmm|belki de|sen bilirsin|göz kırp|çaktırma|ne dersin"),
    ("laugh", r"güle|kahkaha|hahaha|ha ha|kıkırda|eğlen|komik"),
    ("curious", r"\?|merak|acaba|bakalım|neden|ne var|nerede|kim"),
    ("happy", r"harika|süper|çok güzel|bayram|sevin|mutlu|teşekkür|aferin|bravo|yaşasın|sarıl|!"),
]
_RX = [(m, re.compile(p, re.I)) for m, p in RULES]


def mood_for(text, valence=None):
    t = str(text or "")
    for m, rx in _RX:
        if rx.search(t):
            return m
    if valence is not None:
        try:
            v = float(valence)
            if v < 0.3:
                return "sad"
            if v > 0.75:
                return "happy"
        except (TypeError, ValueError):
            pass
    return "neutral"
