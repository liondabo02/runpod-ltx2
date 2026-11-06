"""Small talk is a conversation, not a mission.

A greeting, a thanks or a short question must never become three department
tasks. This module decides whether a message is chitchat and answers it directly.
"""

from __future__ import annotations

import re

GREETINGS = (
    "merhaba", "selam", "selamlar", "günaydın", "iyi akşamlar", "iyi geceler",
    "nasılsın", "naber", "hello", "hi", "hey", "teşekkür", "tesekkur", "sağol",
    "sagol", "eyvallah", "tamam", "ok", "peki", "anladım", "anladim", "görüşürüz",
)

QUESTION_HINTS = ("nasılsın", "ne haber", "naber", "kimsin", "adın ne", "orada mısın")


def is_chitchat(message: str) -> bool:
    """True when the message is a greeting/thanks/short social line."""

    text = re.sub(r"\s+", " ", message or "").strip().casefold()
    if not text:
        return True
    if len(text) <= 40 and any(word in text for word in GREETINGS):
        return True
    if any(hint in text for hint in QUESTION_HINTS):
        return True
    # Yalnızca çok kısa ve fiilsiz satırlar sohbet sayılır; "sistemin durumu
    # nedir" gibi kısa ama gerçek sorular iş olarak kalır.
    words = [word for word in re.findall(r"[a-zçğıöşü0-9]+", text) if len(word) > 2]
    return len(words) <= 2 and len(text) <= 20


def reply(message: str, *, name: str = "AHOS") -> str:
    """A short, honest answer for chitchat; no mission is created."""

    text = (message or "").casefold()
    if any(word in text for word in ("teşekkür", "tesekkur", "sağol", "sagol")):
        return f"Rica ederim. Bir iş vermek istersen yaz; departmana yönlendiririm."
    if any(word in text for word in ("nasılsın", "naber", "ne haber")):
        return (
            "İyiyim, çalışıyorum. Kuyrukta bekleyen işler var; yeni bir şey istersen "
            "yaz, doğru departmana gönderirim."
        )
    if any(word in text for word in ("kimsin", "adın ne")):
        return (
            f"Ben {name} holdinginin CEO'suyum. İşleri departmanlara yönlendirir, "
            "sonucu ve engeli sana raporlarım."
        )
    return "Merhaba. Bir iş vermek istersen yaz: hangi departmanın yapacağını söyler, sonucu takip ederim."
