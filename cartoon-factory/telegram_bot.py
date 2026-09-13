from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parent
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API = f"https://api.telegram.org/bot{TOKEN}"
PY = sys.executable
ALLOWED = {x.strip() for x in os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",") if x.strip()}
PUBLIC_OUTPUT_BASE_URL = os.getenv("PUBLIC_OUTPUT_BASE_URL", "").rstrip("/")
MAX_UPLOAD_MB = int(os.getenv("TELEGRAM_MAX_UPLOAD_MB", "45"))


def tg(method: str, data: dict | None = None, files: dict | None = None) -> dict:
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
    with httpx.Client(timeout=120) as client:
        r = client.post(f"{API}/{method}", data=data or {}, files=files)
        r.raise_for_status()
        payload = r.json()
        if not payload.get("ok"):
            raise RuntimeError(payload)
        return payload


def send_message(chat_id: str, text: str) -> None:
    tg("sendMessage", {"chat_id": chat_id, "text": text})


def send_file_or_link(chat_id: str, path: Path, language: str) -> None:
    size_mb = path.stat().st_size / (1024 * 1024)
    caption = f"{language.upper()} bölüm hazır"
    if size_mb <= MAX_UPLOAD_MB:
        with path.open("rb") as f:
            tg("sendDocument", {"chat_id": chat_id, "caption": caption}, {"document": (path.name, f, "video/mp4")})
        return
    if PUBLIC_OUTPUT_BASE_URL:
        rel = path.relative_to(ROOT / "output").as_posix()
        send_message(chat_id, f"{caption}: {PUBLIC_OUTPUT_BASE_URL}/{quote(rel)}")
    else:
        send_message(chat_id, f"{caption}, ancak dosya Telegram yükleme limitimizi aşıyor ({size_mb:.1f} MB). Sunucu dosyası: {path}")


def write_status(episode_dir: Path, state: str, message: str, extra: dict | None = None) -> None:
    payload = {
        "state": state,
        "message": message,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)
    (episode_dir / "status.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def produce(chat_id: str, idea: str, episode_id: str) -> None:
    episode_dir = ROOT / "output" / episode_id
    episode_dir.mkdir(parents=True, exist_ok=True)
    write_status(episode_dir, "running", "Bölüm hazırlanıyor", {"idea": idea})
    try:
        send_message(chat_id, f"🎬 {episode_id} başladı. Konu: {idea}\n5 dil hazırlanacak: TR, DE, AR, FR, ES.")
        subprocess.run(
            [PY, str(ROOT / "run_pipeline.py"), idea, "--episode-id", episode_id, "--languages", "all"],
            cwd=ROOT,
            check=True,
        )
        manifest_path = episode_dir / "delivery_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        outputs = manifest.get("outputs", {})
        write_status(episode_dir, "completed", "Bölüm tamamlandı", {"outputs": outputs})
        send_message(chat_id, "✅ Bölüm tamamlandı. Dil dosyalarını gönderiyorum.")
        for lang in ["tr", "de", "ar", "fr", "es"]:
            p = Path(outputs.get(lang, ""))
            if p.exists():
                send_file_or_link(chat_id, p, lang)
        send_message(chat_id, "✅ Beş dil teslim edildi.")
    except Exception as exc:
        write_status(episode_dir, "failed", str(exc))
        send_message(chat_id, f"❌ Üretim durdu: {exc}")


def latest_status() -> str:
    output = ROOT / "output"
    if not output.exists():
        return "Henüz bölüm üretimi yok."
    statuses = sorted(output.glob("*/status.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not statuses:
        return "Henüz durum kaydı yok."
    data = json.loads(statuses[0].read_text(encoding="utf-8"))
    episode_id = statuses[0].parent.name
    return f"{episode_id}: {data.get('state')} — {data.get('message')}"


def handle_message(message: dict) -> None:
    chat_id = str(message.get("chat", {}).get("id", ""))
    if not chat_id:
        return
    if ALLOWED and chat_id not in ALLOWED:
        send_message(chat_id, "Bu bot bu sohbet için yetkili değil.")
        return
    text = str(message.get("text", "")).strip()
    if not text:
        send_message(chat_id, "Bir kelime, konu veya hikâye yaz. Örn: paylaşmak")
        return

    if text in {"/start", "/help"}:
        send_message(
            chat_id,
            "🎬 Cartoon Factory\n\n"
            "Bir kelime bile yazabilirsin: paylaşmak\n"
            "Ya da: Aden ve Kaan parkta paylaşmayı öğrensin, Harun çözsün.\n\n"
            "Komutlar:\n/status — son üretim durumu\n/help — yardım\n\n"
            "Normal mesaj = yeni 8 dakikalık bölüm (TR/DE/AR/FR/ES).",
        )
        return
    if text == "/status":
        send_message(chat_id, latest_status())
        return

    episode_id = datetime.now().strftime("episode_%Y%m%d_%H%M%S")
    thread = threading.Thread(target=produce, args=(chat_id, text, episode_id), daemon=True)
    thread.start()
    send_message(chat_id, f"📥 Komut alındı: {episode_id}")


def main() -> None:
    if not TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN")
    offset = 0
    send_message(os.getenv("TELEGRAM_ADMIN_CHAT_ID"), "🟢 Cartoon Factory bot başladı.") if os.getenv("TELEGRAM_ADMIN_CHAT_ID") else None
    while True:
        try:
            with httpx.Client(timeout=70) as client:
                r = client.get(f"{API}/getUpdates", params={"timeout": 50, "offset": offset})
                r.raise_for_status()
                payload = r.json()
            for update in payload.get("result", []):
                offset = max(offset, int(update["update_id"]) + 1)
                if "message" in update:
                    handle_message(update["message"])
        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f"telegram loop error: {exc}", flush=True)
            time.sleep(3)


if __name__ == "__main__":
    main()
