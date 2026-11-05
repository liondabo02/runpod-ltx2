"""Worker mind — çalışanın duygusal ve biliysel durumunu takip eder.

- emotion(mind, ctx) -> dict
  · heartbeat.mood_from ile aynı formül; self_model["mood"] olarak sakla
  · mind (brain dict) güncellenir
"""

from __future__ import annotations

import json


def emotion(mind: dict, ctx: dict) -> dict:
    """Calışanın duygusal durumunu hesaplar ve mind'e kaydeder.

    Args:
        mind: Mevcut mind dict (worker brain'i)
        ctx: Bağlam dict (pending, failures, delivered, quality_rate, last_task vb.)

    Returns:
        Güncellenmiş mind dict (mood kaydedildi)
    """
    # Heartbeat.mood_from benzer formül: pending, failures, delivered, quality_rate üzerinden
    pending = int(ctx.get("pending") or 0)
    failures = int(ctx.get("failures") or 0)
    delivered = int(ctx.get("delivered") or 0)
    quality = float(ctx.get("quality_rate") or 0.0)

    # Mood hesaplama: heartbeat.mood_from benzetmesi
    # Yüksek engel (high barrier): failures > delivered => stres
    # Düşük engel (low barrier): failures <= delivered => motive
    if failures > delivered:
        mood = "stres"
    else:
        mood = "motive"

    # Mind'e mood kaydet (zaten varsa üzerine yazar, append yapmaz)
    mind["mood"] = mood
    
    return mind
