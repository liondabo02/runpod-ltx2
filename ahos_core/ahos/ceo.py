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
    delivery_rate = report.get("delivery_rate", 0.0)
    missions = report.get("missions", 0)
    # Queue closure is an administrative signal, not product delivery evidence.
    queue_completion_rate = None
    queue_missions = 0
    try:
        import sqlite3

        db = runtime_dir / "company-service.db"
        if db.exists():
            with sqlite3.connect(db) as con:
                counts = dict(con.execute(
                    "select status, count(*) from missions group by status"
                ).fetchall())
            completed = counts.get("completed", 0)
            blocked = counts.get("blocked", 0)
            pending = counts.get("pending", 0)
            total = sum(counts.values())
            if total:
                queue_completion_rate = completed / total
                queue_missions = total
    except Exception:  # noqa: BLE001 - kuyruk okunamazsa analiz değeri kalır
        pass
    return {
        "daemon": daemon.get("status", "bilinmiyor"),
        "executor": daemon.get("executor_mode", ""),
        "delivery_rate": delivery_rate,
        "missions": missions,
        "queue_completion_rate": queue_completion_rate,
        "queue_missions": queue_missions,
        "delivery_scope": "daemon mission evidence; not full product acceptance",
        "top": [item["label"] for item in report.get("top_causes", [])[:2]],
        "knowledge": knowledge.stats(runtime_dir),
        "skills": _skills_count(runtime_dir),
    }


def _looks_like_goal(message: str) -> bool:
    lowered = message.casefold()
    verbs = ("geliştir", "iyileştir", "büyüt", "yenile", "dönüştür", "baştan yap")
    return any(verb in lowered for verb in verbs) and len(message.strip()) > 10


def _looks_like_work(message: str) -> bool:
    lowered = message.casefold()
    verbs = (
        "yap", "ekle", "hazırla", "hazirla", "oluştur", "olustur", "kur",
        "geliştir", "gelistir", "düzelt", "duzelt", "yaz", "planla",
        "görev ver", "gorev ver", "iş ver", "is ver", "çalıştır", "calistir",
        "başlat", "baslat", "üret", "uret", "tamamla", "onar", "iyileştir",
        "iyilestir", "güncelle", "guncelle",
    )
    return any(verb in lowered for verb in verbs) and len(message.strip()) > 12


def _facts_text(runtime: Path, state: dict) -> str:
    """The only material the CEO may speak from."""

    try:
        from .ceo_brain import diagnose, explain

        diagnosis = diagnose(runtime)
        lines = [explain(diagnosis)]
    except Exception:  # noqa: BLE001 - tanı isteğe bağlı
        diagnosis = None
        lines = []
    lines += [
        f"daemon={state['daemon']} mod={state['executor'] or '-'}",
        f"dosya_degisim_kanitli_teslim_orani=%{round(state['delivery_rate'] * 100)} gorev={state['missions']} (tam ürün kabulü değildir)",
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
        f"Holding durumu: daemon {state['daemon']}",
        f"dosya değişim kayıtlarına göre teslim oranı %{round(state['delivery_rate'] * 100)} ({state['missions']} görev; tam ürün kabulü ayrıca gerekir)",
        f"bilgi ağında {state['knowledge']['documents']} belge / {state['knowledge']['chunks']} parça",
    ]
    if state["top"]:
        parts.append("en sık sorun: " + ", ".join(state["top"]))
    if _looks_like_work(message):
        parts.append("isteğini görev olarak kuyruğa aldım; işçiler sırayla ele alacak.")
    else:
        parts.append("bir iş vermek istersen yaz; departmana yönlendirip göreve bölerim.")
    return ". ".join(parts) + "."


def _department_for(text: str) -> str:
    """Metne göre departman seç (hızlı, deterministik yönlendirme)."""

    low = text.casefold()
    table = (
        ("oyun", ("oyun", "mipiluna", "bölüm", "level", "sokak oyun")),
        ("creative", ("stüdyo", "çizgi film", "jenerik", "video", "senaryo", "dublaj")),
        ("software", ("kod", "yazılım", "hata", "bug", "api")),
        ("data", ("rapor", "veri", "analiz", "istatistik", "raporu")),
        ("finance", ("bütçe", "harcama", "maliyet", "fatura", "usd")),
        ("guvenlik", ("güvenlik", "denetim", "kilit", "şüphe")),
        ("quality", ("kalite", "kabul", "test", "doğrulama")),
        ("marketing", ("tanıtım", "pazarlama", "reklam", "sosyal medya")),
        ("research", ("araştır", "incele", "kaynak", "benchmark")),
    )
    for department, words in table:
        if any(word in low for word in words):
            return department
    return "genel"


def _clean_reply(raw: str) -> str:
    """Modelin düz metin yazmasını garanti et; JSON gelirse içinden mesajı çıkar."""

    text = (raw or "").strip()
    if not text:
        return ""
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    if text.lstrip().startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            for key in ("message", "cevap", "reply", "summary", "özet"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()[:600]
            solutions = payload.get("solutions") or payload.get("steps")
            if isinstance(solutions, list) and solutions:
                return "; ".join(str(item) for item in solutions[:3])[:600]
    return text[:600]


def _model_reply(runtime, text, state, routed, tasks) -> str:
    """İsteğe bağlı model cevabı; başarısız olursa boş döner (asılmaz)."""

    try:
        from dataclasses import replace as _replace

        from .llm_executor import http_transport, load_settings, _paid_guard

        settings = load_settings()
        if settings is None:
            return ""
        settings = _replace(
            settings,
            model=os.environ.get("AHOS_CEO_MODEL", settings.model),
            base_url=os.environ.get(
                "AHOS_CEO_BASE_URL",
                os.environ.get("AHOS_LLM_BASE_URL", "http://127.0.0.1:11500/v1"),
            ),
            api_key=os.environ.get("AHOS_CEO_API_KEY", "local-only"),
            timeout_seconds=120.0,
            max_tokens=300,
        )
        prompt = (
            f"Sahip şöyle dedi: {text}\n\n"
            f"GERÇEKLER:\n{_facts_text(runtime, state)}"
            + (f"\nYönlendirilen departman: {routed['department']} ({tasks} görev)." if routed else "")
            + "\n\nSahibe 2-4 cümlelik DÜZ METİN cevap ver. JSON, madde işareti veya kod bloğu yazma."
        )
        try:
            extra = knowledge.context(runtime, text)
            if extra:
                prompt += "\n\n" + extra
        except Exception:  # noqa: BLE001
            pass
        if _paid_guard(settings) is not None:
            return ""
        reply = _clean_reply(http_transport(SYSTEM, prompt, settings))
        normalized = reply.casefold().strip(" .!?")
        if not normalized or normalized in text.casefold() or len(normalized) < 25:
            return ""
        return reply
    except Exception:  # noqa: BLE001 - model isteğe bağlı
        return ""


def answer(runtime_dir: str | Path, message: str) -> dict:
    """Reply to the owner; create work when the message asks for it."""

    runtime = Path(runtime_dir)
    try:
        from .daemon import _load_model_env

        _load_model_env(runtime)
    except Exception:  # noqa: BLE001 - config is optional
        pass
    # model.env ücretli sağlayıcıya işaret edebilir; sağlıklı ücretsiz kaynak
    # (tünel/yerel) varsa onu kullan. Bu yüzden zincir en SON uygulanır.
    if os.environ.get("AHOS_PROVIDER_CHAIN", "").strip().lower() in {"1", "true", "yes", "on"}:
        try:
            from .providers import apply_chain_to_env

            apply_chain_to_env()
        except Exception:  # noqa: BLE001 - sağlayıcı seçimi cevabı engellemesin
            pass
    text = message.strip()
    if not text:
        return {"reply": "Bir şey yazman yeterli.", "routed": None, "tasks": 0, "mode": "empty"}

    # --- CEO ofisi yetkileri (deterministik, model gerekmez) ---
    low = text.casefold()
    try:
        from . import ceo_office
    except Exception:  # noqa: BLE001 - ofis modülü isteğe bağlı
        ceo_office = None

    if ceo_office is not None:
        if any(key in low for key in ("hedef koy", "hedef belirle", "hedef:")):
            objective = text.split(":", 1)[-1].strip() if ":" in text else text
            departments = tuple(
                dep for dep in ("oyun", "software", "creative", "data", "quality")
                if dep in low
            ) or ("oyun",)
            record = ceo_office.set_goal(runtime, objective, departments)
            reply = (
                f"Hedef kaydedildi: {record['goal_id']}. "
                f"{len(record['missions'])} departmana görev bırakıldı "
                f"({', '.join(departments)})."
            )
            _record(runtime, "owner", text)
            _record(runtime, "ceo", reply, {"routed": record, "tasks": len(record["missions"]), "mode": "goal"})
            return {"reply": reply, "routed": record, "tasks": len(record["missions"]), "mode": "goal"}

        if any(key in low for key in ("brifing", "günlük rapor", "gunluk rapor", "durum raporu")):
            brief = ceo_office.daily_brief(runtime)
            reply = "Günlük brifing:\n" + brief.text()
            _record(runtime, "owner", text)
            _record(runtime, "ceo", reply, {"mode": "brief"})
            return {"reply": reply, "routed": None, "tasks": 0, "mode": "brief"}

        if any(key in low for key in ("araştır", "arastir", "incele", "analiz et")):
            from . import subagent as subagent_mod

            run = subagent_mod.run(runtime, text)
            reply = "Araştırma özeti (izole alt-ajan):\n" + run.summary
            _record(runtime, "owner", text)
            _record(runtime, "ceo", reply, {"mode": "subagent", "run": run.run_id})
            return {"reply": reply, "routed": {"subagent": run.run_id}, "tasks": 0, "mode": "subagent"}

        if any(key in low for key in ("değerlendir", "degerlendir", "performans", "zayıf halka", "zayif halka")):
            decision = ceo_office.decide(runtime, text)
            reply = decision["answer"]
            _record(runtime, "owner", text)
            _record(runtime, "ceo", reply, {"mode": "decision", "action": decision["action"]})
            return {"reply": reply, "routed": None, "tasks": 0, "mode": "decision"}

    from .chitchat import is_chitchat, reply as chat_reply

    status_query = any(
        word in text.casefold()
        for word in ("durum", "nasıl", "ne alem", "ne durumda", "özet", "rapor ver")
    )
    if is_chitchat(text) and not status_query:
        answer_text = chat_reply(text)
        _record(runtime, "owner", text)
        _record(runtime, "ceo", answer_text, {"routed": None, "tasks": 0, "mode": "chitchat"})
        return {"reply": answer_text, "routed": None, "tasks": 0, "mode": "chitchat"}

    state = _snapshot(runtime)
    routed = None
    tasks = 0
    mode = "deterministic"

    # İstek analizi + hukuk denetimi (görev dağıtımı tahminle yapılmaz).
    try:
        from .intent import analyze as analyse_intent
        from .legal import review as legal_review

        intent = analyse_intent(text)
        legal = legal_review(text)
    except Exception:  # noqa: BLE001 - analiz isteğe bağlı
        intent, legal = None, None

    if legal is not None and legal.needs_owner_confirmation:
        from .autonomous_company import PersistentMissionQueue
        from .legal import review as _legal_review  # noqa: F401 - tip netliği

        departments = [dep for dep, _score in (intent.departments if intent else ())][:2] or ["hukuk"]
        if "hukuk" not in departments:
            departments.append("hukuk")
        mission_ids: list[str] = []
        try:
            queue = PersistentMissionQueue(runtime / "company-service.db")
            for department in departments:
                mission_id = f"CMD-{department}-legal-{int(time.time())}"
                queue.enqueue(
                    mission_id=mission_id,
                    objective=(
                        f"{text} — HUKUK NOTU: yalnız yasal alternatifle ilerle. "
                        + (legal.alternatives[0] if legal.alternatives else "")
                    ),
                    primary_department=department,
                    max_attempts=1,
                    replace_existing=True,
                )
                mission_ids.append(mission_id)
        except Exception:  # noqa: BLE001 - kuyruk isteğe bağlı
            pass
        reply = (
            legal.text()
            + "\n\nİsteğini bu yasal çerçevede göreve dönüştürdüm ("
            + ", ".join(departments)
            + "). Onaylarsan doğrudan ilerlerim."
        )
        _record(runtime, "owner", text)
        _record(runtime, "ceo", reply, {"mode": "legal", "missions": mission_ids})
        return {"reply": reply, "routed": {"missions": mission_ids, "intent": intent.summary() if intent else ""}, "tasks": len(mission_ids), "mode": "legal"}

    if _looks_like_work(text):
        # İşi SENKRON çalıştırma: kuyruğa bırak, daemon işlesin.
        department = (
            intent.departments[0][0] if intent and intent.departments and intent.departments[0][1] >= 2
            else _department_for(text)
        )
        # Örnek verildiyse: önce örneği çöz, sonra uygula.
        if intent is not None and intent.example:
            text = (
                f"{text}\n\nÖRNEK TERSİNE MÜHENDİSLİK: kaynak={intent.example} "
                f"({intent.example_kind}). Önce yapıyı/akışı/tasarımı çöz, "
                "sonra aynı sonucu özgün içerikle uygula."
            )
        try:
            from .autonomous_company import PersistentMissionQueue

            queue = PersistentMissionQueue(runtime / "company-service.db")
            mission_id = f"CMD-{department}-ceo-{int(time.time())}"
            queue.enqueue(
                mission_id=mission_id,
                objective=text,
                primary_department=department,
                max_attempts=1,
                replace_existing=True,
            )
            if not mission_id:
                from .collab import launch as collab_launch

                collaboration = collab_launch(runtime, text)
                routed = {
                    "collaboration": collaboration.ticket,
                    "departments": [part.department for part in collaboration.parts],
                    "missions": collaboration.missions,
                }
                tasks = len(collaboration.missions)
            else:
                routed = {"department": department, "id": department, "mission": mission_id}
            tasks = 1
            # Fikir kaydı: panelde "bekleyen fikir" sayacı ve izlenebilirlik için.
            try:
                ideas = runtime / "ideas"
                ideas.mkdir(parents=True, exist_ok=True)
                (ideas / f"{mission_id}.json").write_text(
                    json.dumps(
                        {
                            "idea_id": mission_id,
                            "text": text,
                            "department": department,
                            "mission_id": mission_id,
                            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            "source": "ceo",
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except OSError:
                pass
        except Exception:  # noqa: BLE001 - kuyruk hatası cevabı engellemesin
            routed = {"department": department, "id": department}
            tasks = 0

    reply = ""
    # Varsayılan: deterministik, gerçek veriye dayalı cevap (hızlı ve güvenilir).
    # Model yalnızca açıkça istenirse kullanılır: AHOS_CEO_MODEL_ENABLED=1
    if os.environ.get("AHOS_CEO_MODEL_ENABLED", "").strip() in {"1", "true", "yes", "on"}:
        reply = _model_reply(runtime, text, state, routed, tasks)
        if reply:
            mode = "model:" + os.environ.get("AHOS_CEO_MODEL", "qwen2.5-coder:7b")

    diagnostic = any(
        word in text.casefold()
        for word in ("sorun", "analiz", "neden", "kök", "teslim", "engel", "hata")
    )
    if diagnostic:
        try:
            from . import ceo_brain

            explanation = ceo_brain.explain(ceo_brain.diagnose(runtime))
            reply = (reply + "\n\n" if reply else "") + explanation
            if any(word in text.casefold() for word in ("çöz", "coz", "düzelt", "gider")):
                created = ceo_brain.dispatch(runtime)
                if created:
                    reply += "\n\nGörev açıldı: " + ", ".join(
                        item["title"][:60] for item in created
                    )
                    routed = routed or {"department": created[0]["department"], "id": created[0]["department"]}
        except Exception:  # noqa: BLE001 - tanı isteğe bağlı
            pass
    if not reply:
        reply = _offline_reply(state, text)
    elif len(reply.strip()) < 60:
        # Model anlamsız/kısa bir şey döndürdüyse gerçek durum özetini ekle.
        reply = reply.strip() + "\n\n" + _offline_reply(state, text)

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
