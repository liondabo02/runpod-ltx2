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
    "Sen AHOS holdinginin CEO'susun. Yalnızca sana verilen GERÇEKLERLE konuş; "
    "veride olmayan bir şeyi uydurma. Türkçe, kısa ve net ol. Cevabında en az bir "
    "somut sayı kullan ve 1-3 uygulanabilir sonraki adım öner. Genel geçer "
    "danışmanlık cümleleri kurma; holdingin gerçek işlerine bağlı kal."
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


def _skills_count(runtime_dir: Path) -> int:
    try:
        from .skills import stats

        return int(stats(runtime_dir).get("cards") or 0)
    except Exception:  # noqa: BLE001
        return 0


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
        "skills": _skills_count(runtime_dir),
    }


def _looks_like_work(message: str) -> bool:
    lowered = message.casefold()
    verbs = ("yap", "ekle", "hazırla", "oluştur", "kur", "geliştir", "düzelt", "yaz", "planla")
    return any(verb in lowered for verb in verbs) and len(message.strip()) > 12


def _facts_text(runtime: Path, state: dict) -> str:
    """The only material the CEO may speak from."""

    lines = [
        f"daemon={state['daemon']} mod={state['executor'] or '-'}",
        f"teslim_orani=%{round(state['delivery_rate'] * 100)} gorev={state['missions']}",
        "en_sik_sorun=" + (", ".join(state["top"]) if state["top"] else "yok"),
        f"bilgi_agi={state['knowledge']['documents']} belge/{state['knowledge']['chunks']} parca",
        f"beceri_kartlari={state.get('skills', 0)}",
    ]
    try:
        backlog = [
            json.loads(line).get("title", "")
            for line in (runtime / "self-improvement.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if backlog:
            lines.append("kalite_kuyrugu=" + " | ".join(backlog[:2]))
    except (OSError, json.JSONDecodeError):
        pass
    try:
        rows = (runtime / "daemon-missions.jsonl").read_text(encoding="utf-8").splitlines()[-3:]
        recent = []
        for line in rows:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            recent.append(f"{row.get('status')}/{row.get('changed_files')} dosya")
        if recent:
            lines.append("son_gorevler=" + ", ".join(recent))
    except OSError:
        pass
    return "\n".join(f"- {line}" for line in lines)


def _has_number(text: str) -> bool:
    return any(char.isdigit() for char in text)


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
                f"GERÇEKLER:\n{_facts_text(runtime, state)}"
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
    elif not _has_number(reply):
        reply += "\n" + _offline_reply(state, text)

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
