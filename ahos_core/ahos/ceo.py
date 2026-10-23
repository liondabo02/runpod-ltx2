"""The CEO agent: the person the owner talks to.

The owner writes in plain language. The CEO answers with the holding's real
state and, when the message asks for work, turns it into an idea (routed to a
department, split into tasks). With a model configured it answers naturally;
without one (offline or rate limited) it still answers with a deterministic
status reply, so the owner is never left without a voice.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from . import knowledge
from .failure_analytics import analyse
from .ideas import submit

SYSTEM = (
    "Sen AHOS holdinginin CEO'sun. Türkçe, kısa ve net konuş. Sahibine holdingin "
    "gerçek durumunu söyle, gerekiyorsa iş öner. Elinde olmayan veriyi uydurma. "
    "Yanıtı yalnızca düz metin olarak ver."
)


def _thread_path(runtime_dir: str | Path) -> Path:
    return Path(runtime_dir) / "ceo-thread.jsonl"


def _record(runtime_dir: str | Path, role: str, text: str, extra: dict | None = None) -> None:
    path = _thread_path(runtime_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "role": role, "text": text[:2000]}
    if extra:
        row.update(extra)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def thread(runtime_dir: str | Path, limit: int = 20) -> list[dict]:
    path = _thread_path(runtime_dir)
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def _snapshot(runtime_dir: Path) -> dict:
    daemon = {}
    try:
        daemon = json.loads((runtime_dir / "daemon-state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    report = analyse(runtime_dir)
    return {
        "daemon": daemon.get("status", "bilinmiyor"),
        "executor": daemon.get("executor_mode", ""),
        "delivery_rate": report.get("delivery_rate", 0.0),
        "missions": report.get("missions", 0),
        "top": [item["label"] for item in report.get("top_causes", [])[:2]],
        "knowledge": knowledge.stats(runtime_dir),
    }


def _looks_like_work(message: str) -> bool:
    lowered = message.casefold()
    verbs = ("yap", "ekle", "hazırla", "oluştur", "kur", "geliştir", "düzelt", "yaz", "planla")
    return any(verb in lowered for verb in verbs) and len(message.strip()) > 12


def _offline_reply(state: dict, message: str) -> str:
    parts = [
        f"Şu an model bağlantısı yok; holdingin durumu: daemon {state['daemon']}",
        f"teslim oranı %{round(state['delivery_rate'] * 100)} ({state['missions']} görev)",
        f"bilgi ağında {state['knowledge']['documents']} belge / {state['knowledge']['chunks']} parça",
    ]
    if state["top"]:
        parts.append("en sık sorun: " + ", ".join(state["top"]))
    if _looks_like_work(message):
        parts.append("isteğini görev olarak kuyruğa aldım; işçiler sırayla ele alacak.")
    else:
        parts.append("bir iş vermek istersen yaz; departmana yönlendirip göreve bölerim.")
    return ". ".join(parts) + "."


def answer(runtime_dir: str | Path, message: str) -> dict:
    """Reply to the owner; create work when the message asks for it."""

    runtime = Path(runtime_dir)
    try:
        from .daemon import _load_model_env

        _load_model_env(runtime)
    except Exception:  # noqa: BLE001 - config is optional
        pass
    text = message.strip()
    if not text:
        return {"reply": "Bir şey yazman yeterli.", "routed": None, "tasks": 0, "mode": "empty"}

    state = _snapshot(runtime)
    routed = None
    tasks = 0
    mode = "offline"

    if _looks_like_work(text):
        try:
            from .owner_console import build_default_console

            console = build_default_console(runtime)
            idea = submit(console, runtime, text)
            routed = {"department": idea.department_name, "id": idea.department_id}
            tasks = len(idea.tasks)
        except Exception:  # noqa: BLE001 - routing must not block the reply
            routed = None

    reply = ""
    try:
        from .llm_executor import http_transport, load_settings

        settings = load_settings()
        if settings is not None:
            prompt = (
                f"Sahip şöyle dedi: {text}\n\n"
                f"Holding durumu: daemon={state['daemon']}, mod={state['executor']}, "
                f"teslim oranı=%{round(state['delivery_rate'] * 100)}, "
                f"görev={state['missions']}, bilgi ağı={state['knowledge']}."
                + (f"\nYönlendirilen departman: {routed['department']} ({tasks} görev)." if routed else "")
                + "\n\nSahibe 2-4 cümleyle cevap ver."
            )
            extra = knowledge.context(runtime, text)
            if extra:
                prompt += "\n\n" + extra
            reply = http_transport(SYSTEM, prompt, settings).strip()
            mode = f"model:{settings.model}"
    except Exception:  # noqa: BLE001 - fall back to the deterministic voice
        reply = ""

    if not reply:
        reply = _offline_reply(state, text)

    _record(runtime, "owner", text)
    _record(runtime, "ceo", reply, {"routed": routed, "tasks": tasks, "mode": mode})
    return {"reply": reply, "routed": routed, "tasks": tasks, "mode": mode}


def main(argv: list[str] | None = None) -> int:
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    runtime = Path("runtime")
    if "--runtime-dir" in args:
        position = args.index("--runtime-dir")
        runtime = Path(args[position + 1])
    message = " ".join(arg for arg in args if not arg.startswith("--") and arg != str(runtime)).strip()
    if not message:
        for row in thread(runtime):
            print(f"{row['role']}: {row['text']}")
        return 0
    result = answer(runtime, message)
    print(result["reply"])
    if result["routed"]:
        print(f"(yönlendirildi: {result['routed']['department']} · {result['tasks']} görev · {result['mode']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
