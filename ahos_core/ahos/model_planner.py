"""Model-backed work selection.

The fixed growth cycle eventually runs out: every objective has been done for
the day and the loop goes idle. A holding does not stop there — it decides what
to do next. This module asks the configured model for a short, concrete list of
improvements grounded in the current projects, validates the answer strictly and
hands it back as ordinary directives.
"""

from __future__ import annotations

import json
import os
import re
from typing import Iterable, Mapping

from .llm_executor import ModelError, http_transport, load_settings, parse_json_object

SYSTEM_PROMPT = (
    "Sen bir yazılım holdinginin planlama kurulunun başkanısın. Sana verilen "
    "departmanlar, projeler ve son yapılan işler listesine bakarak en değerli üç "
    "somut iyileştirme görevi öner. Görevler tek bir mühendisin 30 dakikada "
    "bitirebileceği kadar küçük, ölçülebilir ve mevcut işlerin tekrarı olmayan "
    "şeyler olmalı. Yalnızca JSON döndür, başka metin yazma: "
    '{"objectives":[{"department":"<departman-id>","title":"<kısa görev>",'
    '"why":"<tek cümle gerekçe>"}]}'
)

MIN_TITLE = 12
MAX_TITLE = 160


def build_context(
    departments: Mapping[str, str],
    projects: Mapping[str, Iterable[str]],
    recent: Iterable[str],
    agents: Mapping[str, Iterable[str]] | None = None,
) -> str:
    """Compact, deterministic context: no file bodies, only shape and history."""

    recent_list = list(recent)
    lines = ["Departmanlar:"]
    for department_id, name in sorted(departments.items()):
        names = ", ".join(sorted(projects.get(department_id, ()))) or "proje yok"
        lines.append(f"- {department_id} ({name}) → {names}")
    if agents:
        lines.append("")
        lines.append("Ekip (kim hangi yetkinliğe sahip):")
        for agent_id, capabilities in sorted(agents.items()):
            joined = ", ".join(list(capabilities)[:6]) or "genel"
            lines.append(f"- {agent_id}: {joined}")
    lines.append("")
    lines.append("Son yapılan işler (tekrar önermeyin):")
    for objective in recent_list[:20]:
        lines.append(f"- {objective}")
    if not recent_list:
        lines.append("- (kayıt yok)")
    return "\n".join(lines)


def _extract_json(raw: str) -> dict:
    return parse_json_object(raw)


def validate_objectives(
    payload: Mapping[str, object],
    departments: Mapping[str, str],
    recent: Iterable[str] = (),
    limit: int = 3,
) -> list[dict]:
    """Keep only well-formed, in-scope, non-duplicate objectives."""

    raw = payload.get("objectives")
    if not isinstance(raw, list):
        return []

    seen = {str(item).strip().casefold() for item in recent}
    cleaned: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        department = str(item.get("department") or "").strip()
        title = " ".join(str(item.get("title") or "").split())
        why = " ".join(str(item.get("why") or "").split())
        if department not in departments:
            continue
        if not (MIN_TITLE <= len(title) <= MAX_TITLE):
            continue
        key = title.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append({"department": department, "title": title, "why": why[:200]})
        if len(cleaned) >= limit:
            break
    return cleaned


def propose_objectives(
    departments: Mapping[str, str],
    projects: Mapping[str, Iterable[str]],
    recent: Iterable[str] = (),
    limit: int = 3,
    settings=None,
    transport=None,
    agents: Mapping[str, Iterable[str]] | None = None,
) -> list[dict]:
    """Ask the model for the next objectives; empty list on any failure."""

    settings = settings or load_settings()
    if settings is None:
        return []
    # Planlama turu döngüyü kilitlememeli: kısa ve sabit bir zaman bütçesi.
    try:
        from dataclasses import replace

        budget = int(os.environ.get("AHOS_PLANNER_TIMEOUT", "20"))
        settings = replace(
            settings,
            timeout_seconds=min(int(settings.timeout_seconds or budget), budget),
        )
    except Exception:  # noqa: BLE001 - planning must not fail on odd settings
        pass
    transport = transport or http_transport
    prompt = build_context(departments, projects, recent, agents)
    try:
        raw = transport(SYSTEM_PROMPT, prompt, settings)
    except ModelError:
        return []
    except Exception:  # noqa: BLE001 - planning must never break the loop
        return []
    try:
        payload = _extract_json(raw)
    except ModelError:
        return []
    return validate_objectives(payload, departments, recent, limit)
