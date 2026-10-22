#!/usr/bin/env python3
"""Cloud worker: produces patch proposals while the PC is off.

Runs on the Oracle VM with only the Python standard library. It reads a task
list and a synced copy of the project, asks a free model for a strict JSON
change set, validates it (paths inside the project, exact find/replace rules)
and writes one proposal per task into the outbox. The local AHOS imports and
verifies these later, so nothing unverified ever reaches the product.

Environment:
    OPENROUTER_KEY   API key (required)
    AHOS_MODEL       primary model id (default: poolside/laguna-s-2.1:free)
    AHOS_MODELS      comma separated fallbacks
    AHOS_TASKS       tasks.json path (default ~/ahos/tasks.json)
    AHOS_PROJECT     synced project root (default ~/ahos/project)
    AHOS_OUTBOX      outbox dir (default ~/ahos/outbox)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HOME = Path(os.environ.get("HOME", str(Path.home())))
TASKS = Path(os.environ.get("AHOS_TASKS", HOME / "ahos" / "tasks.json"))
PROJECT = Path(os.environ.get("AHOS_PROJECT", HOME / "ahos" / "project"))
OUTBOX = Path(os.environ.get("AHOS_OUTBOX", HOME / "ahos" / "outbox"))
KEY = os.environ.get("OPENROUTER_KEY", "")
MODELS = [
    item.strip()
    for item in (
        os.environ.get("AHOS_MODELS")
        or os.environ.get("AHOS_MODEL")
        or "poolside/laguna-s-2.1:free,nvidia/nemotron-3.5-lightning:free,openrouter/free"
    ).split(",")
    if item.strip()
]
TEXT_SUFFIXES = {".html", ".css", ".js", ".json", ".md", ".txt", ".svg"}

SYSTEM = (
    "Sen kıdemli bir yazılım mühendisisin. Yalnızca JSON döndür. "
    '{"summary":"...","edits":[{"path":"www/x.js","find":"...","replace":"..."}]} '
    "Kurallar: en fazla 2 düzenleme; find dosyada birebir geçmeli (en fazla 300 "
    "karakter); yeni dosya için find yerine content kullan."
)


def project_files(limit: int = 120) -> list[str]:
    files: list[str] = []
    for path in sorted(PROJECT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        files.append(path.relative_to(PROJECT).as_posix())
        if len(files) >= limit:
            break
    return files


def prompt_for(task: str) -> str:
    files = project_files()
    samples: list[str] = []
    for name in ("www/index.html", "index.html"):
        candidate = PROJECT / name
        if candidate.exists():
            samples.append(f"### {name}\n```\n{candidate.read_text(encoding='utf-8', errors='replace')[:6000]}\n```")
            break
    return (
        f"Görev: {task}\n\nDosyalar:\n" + "\n".join(files) +
        "\n\n" + "\n\n".join(samples) +
        "\n\nYalnızca proje içindeki dosyaları düzenle. Yanıtı sadece JSON olarak ver."
    )


LOCAL_URL = os.environ.get("AHOS_LOCAL_URL", "http://127.0.0.1:11434/v1")
LOCAL_MODEL = os.environ.get("AHOS_LOCAL_MODEL", "qwen2.5-coder:3b")
STOP_FILE = Path(os.environ.get("AHOS_CLOUD_STOP", HOME / "ahos" / "STOP"))
MAX_TASKS_PER_RUN = int(os.environ.get("AHOS_MAX_TASKS_PER_RUN", "2"))
MAX_TASKS_IN_LIST = int(os.environ.get("AHOS_MAX_TASKS_IN_LIST", "40"))
RUN_BUDGET_SECONDS = int(os.environ.get("AHOS_RUN_BUDGET_SECONDS", "1500"))
REQUEST_TIMEOUT = int(os.environ.get("AHOS_REQUEST_TIMEOUT", "120"))


def _chat(system: str, prompt: str, max_tokens: int = 8192, timeout: int = REQUEST_TIMEOUT) -> tuple[str, str]:
    """Try every free remote model, then the VM's own Ollama.

    Free endpoints are rate limited in the evening; the local 3B model is slower
    but always available, which keeps the PC-off pipeline alive without a cloud
    dependency.
    """

    attempts: list[tuple[str, str]] = [
        ("https://openrouter.ai/api/v1/chat/completions", model) for model in MODELS
    ]
    attempts.append((f"{LOCAL_URL.rstrip('/')}/chat/completions", LOCAL_MODEL))

    last_error = "model yok"
    for url, model in attempts:
        headers = {"Content-Type": "application/json"}
        if "openrouter.ai" in url:
            headers["Authorization"] = f"Bearer {KEY}"
        payload = json.dumps(
            {
                "model": model,
                "temperature": 0.2,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            }
        ).encode("utf-8")
        request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=max(10, timeout)) as response:
                body = json.loads(response.read().decode("utf-8"))
            choice = body["choices"][0]
            if str(choice.get("finish_reason") or "") == "length":
                last_error = f"{model}: yanıt kesildi"
                continue
            content = str(choice["message"]["content"] or "")
            if content.strip():
                return model, content
            last_error = f"{model}: boş içerik"
        except urllib.error.HTTPError as exc:
            last_error = f"{model}: HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001
            last_error = f"{model}: {type(exc).__name__}"
    raise RuntimeError(last_error)


def call_model(task: str, timeout: int = REQUEST_TIMEOUT) -> tuple[str, str]:
    return _chat(SYSTEM, prompt_for(task), timeout=timeout)


def parse(raw: str) -> dict:
    start = raw.find("{")
    if start < 0:
        raise ValueError("JSON yok")
    payload, _ = json.JSONDecoder().raw_decode(raw[start:])
    if not isinstance(payload, dict):
        raise ValueError("nesne değil")
    return payload


def validate(payload: dict) -> list[dict]:
    edits = payload.get("edits")
    if not isinstance(edits, list):
        return []
    cleaned: list[dict] = []
    root = PROJECT.resolve()
    for item in edits[:3]:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip().replace("\\", "/")
        if not path:
            continue
        candidate = (root / path).resolve()
        if root != candidate and root not in candidate.parents:
            continue
        find = item.get("find")
        replace = item.get("replace")
        content = item.get("content")
        if isinstance(find, str) and find and isinstance(replace, str):
            if len(find) > 400 or len(replace) > 4000:
                continue
            cleaned.append({"path": path, "find": find, "replace": replace})
        elif isinstance(content, str) and content:
            cleaned.append({"path": path, "content": content})
    return cleaned


PLANNER_SYSTEM = (
    "Sen bir yazılım holdinginin planlama kurulunun başkanısın. Verilen proje "
    "dosyalarına bakarak en değerli üç somut iyileştirme görevini öner. Her görev "
    "tek mühendisin 30 dakikada bitirebileceği kadar küçük olmalı. Yalnızca JSON: "
    '{"objectives":["görev 1","görev 2","görev 3"]}'
)


def propose_tasks(
    existing: list[str], limit: int = 3, timeout: int = REQUEST_TIMEOUT
) -> list[str]:
    """Ask the model for new objectives when the task list has been consumed."""

    files = project_files(60)
    prompt = (
        "Proje dosyaları:\n"
        + "\n".join(files)
        + "\n\nZaten yapılan/yapılacak işler (tekrar önerme):\n"
        + "\n".join(f"- {item}" for item in existing[:30])
        + "\n\nYukarıdakilerden farklı, uygulanabilir üç görev öner."
    )
    try:
        _model, content = _chat(
            PLANNER_SYSTEM, prompt, max_tokens=600, timeout=timeout
        )
        data = parse(content)
        items = data.get("objectives")
        if not isinstance(items, list):
            return []
        seen = {item.strip().casefold() for item in existing}
        fresh: list[str] = []
        for item in items:
            title = " ".join(str(item).split())
            if 12 <= len(title) <= 160 and title.casefold() not in seen:
                seen.add(title.casefold())
                fresh.append(title)
            if len(fresh) >= limit:
                break
        return fresh
    except Exception:  # noqa: BLE001
        return []


def main() -> int:
    if STOP_FILE.exists():
        print(f"acil durdurma etkin: {STOP_FILE} (üretim yapılmadı)")
        return 0
    if not KEY:
        print("OPENROUTER_KEY yok", file=sys.stderr)
        return 2
    if not TASKS.exists():
        print(f"görev listesi yok: {TASKS}", file=sys.stderr)
        return 2

    OUTBOX.mkdir(parents=True, exist_ok=True)
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))
    if not isinstance(tasks, list):
        print("görev listesi bir liste değil", file=sys.stderr)
        return 2

    produced_ids = {path.stem for path in OUTBOX.glob("*.json")}
    titles = {str(task.get("title") or "").strip().casefold() for task in tasks}
    deadline = time.time() + RUN_BUDGET_SECONDS
    produced = 0
    skipped_reason = ""

    for task in tasks:
        if produced >= MAX_TASKS_PER_RUN:
            skipped_reason = f"tur sınırı ({MAX_TASKS_PER_RUN} görev)"
            break
        if time.time() > deadline:
            skipped_reason = "zaman bütçesi doldu"
            break
        title = str(task.get("title") or "").strip()
        if not title:
            continue
        digest = hashlib.sha256(
            f"{task.get('department', '')}|{title}".encode()
        ).hexdigest()[:16]
        destination = OUTBOX / f"{digest}.json"
        if destination.exists() or digest in produced_ids:
            continue
        if STOP_FILE.exists():
            skipped_reason = "acil durdurma"
            break
        remaining = max(10, int(deadline - time.time()))
        try:
            model, raw = call_model(title, timeout=min(REQUEST_TIMEOUT, remaining))
            edits = validate(parse(raw))
        except Exception as exc:  # noqa: BLE001 - bounded failure, keep going
            print(f"[skip] {title[:50]} · {exc}")
            continue
        if not edits:
            print(f"[empty] {title[:50]}")
            continue
        record = {
            "id": digest,
            "task": title,
            "department": task.get("department", ""),
            "model": model,
            "edits": edits,
            "produced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "project": str(PROJECT),
        }
        destination.write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        produced_ids.add(digest)
        produced += 1
        print(f"[ok] {title[:50]} · {len(edits)} düzenleme · {model}")

    # Liste tükendiyse sınırlı sayıda yeni hedef üret (tekrar ve boyut korumalı).
    if produced < MAX_TASKS_PER_RUN and time.time() < deadline:
        pending = any(
            hashlib.sha256(
                f"{task.get('department', '')}|{str(task.get('title') or '').strip()}".encode()
            ).hexdigest()[:16]
            not in produced_ids
            for task in tasks
            if str(task.get("title") or "").strip()
        )
        if not pending and len(tasks) < MAX_TASKS_IN_LIST:
            remaining = max(10, int(deadline - time.time()))
            fresh = propose_tasks(
                [str(task.get("title") or "") for task in tasks],
                timeout=min(REQUEST_TIMEOUT, remaining),
            )
            added = 0
            for title in fresh:
                if title.casefold() in titles:
                    continue
                tasks.append({"department": "oyun", "title": title})
                titles.add(title.casefold())
                added += 1
            if added:
                TASKS.write_text(
                    json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print("yeni hedefler: " + " | ".join(fresh[:added]))
        elif len(tasks) >= MAX_TASKS_IN_LIST:
            skipped_reason = skipped_reason or "görev listesi üst sınırda"

    print(f"üretilen: {produced} · kalan görev: {len(tasks) - produced}")
    if skipped_reason:
        print(f"durma nedeni: {skipped_reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
