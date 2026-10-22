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


def _chat(system: str, prompt: str, max_tokens: int = 8192) -> tuple[str, str]:
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
            with urllib.request.urlopen(request, timeout=180) as response:
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


def call_model(task: str) -> tuple[str, str]:
    return _chat(SYSTEM, prompt_for(task))


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


def propose_tasks(existing: list[str], limit: int = 3) -> list[str]:
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
        _model, content = _chat(PLANNER_SYSTEM, prompt, max_tokens=600)
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
    if not KEY:
        print("OPENROUTER_KEY yok", file=sys.stderr)
        return 2
    if not TASKS.exists():
        print(f"görev listesi yok: {TASKS}", file=sys.stderr)
        return 2
    OUTBOX.mkdir(parents=True, exist_ok=True)
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))
    produced = 0
    for task in tasks:
        title = str(task.get("title") or "").strip()
        if not title:
            continue
        digest = hashlib.sha256(f"{task.get('department','')}|{title}".encode()).hexdigest()[:16]
        destination = OUTBOX / f"{digest}.json"
        if destination.exists():
            continue
        try:
            model, raw = call_model(title)
            edits = validate(parse(raw))
        except Exception as exc:  # noqa: BLE001
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
        destination.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        produced += 1
        print(f"[ok] {title[:50]} · {len(edits)} düzenleme · {model}")

    # Liste tükendiyse modelden yeni hedefler al: PC kapalıyken üretim durmasın.
    produced_ids = {path.stem for path in OUTBOX.glob("*.json")}
    pending: list[str] = []
    for task in tasks:
        title = str(task.get("title") or "").strip()
        if not title:
            continue
        digest = hashlib.sha256(
            f"{task.get('department', '')}|{title}".encode()
        ).hexdigest()[:16]
        if digest not in produced_ids:
            pending.append(title)

    titles = [str(task.get("title") or "") for task in tasks]
    if not pending:
        fresh = propose_tasks(titles)
        if fresh:
            tasks.extend({"department": "oyun", "title": title} for title in fresh)
            TASKS.write_text(
                json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print("yeni hedefler: " + " | ".join(fresh))
        fresh = propose_tasks(titles)
        if fresh:
            tasks.extend({"department": "oyun", "title": title} for title in fresh)
            TASKS.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
            print("yeni hedefler: " + " | ".join(fresh))

    print(f"üretilen: {produced}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
