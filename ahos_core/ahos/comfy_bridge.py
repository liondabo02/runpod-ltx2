"""ComfyUI köprüsü — görsel/video üretim işlerini gerçek motora bağlar.

Akış:
1. workflow JSON (API formatı) yüklenir
2. prompt/parametreler yerleştirilir
3. POST /prompt ile kuyruğa verilir
4. GET /history/<id> ile sonuç beklenir
5. çıktı dosyaları GET /view ile indirilir → runtime/artifacts/renders/

ComfyUI çalışmıyorsa temiz hata döndürür (uydurma yok).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_HOST = "http://127.0.0.1:8188"


class ComfyUnavailable(RuntimeError):
    """ComfyUI erişilemiyor."""


def _request(url: str, *, data: dict | None = None, timeout: float = 30.0) -> dict:
    payload = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"} if payload else {},
        method="POST" if payload else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as exc:
        raise ComfyUnavailable(f"ComfyUI'ye ulaşılamadı ({url}): {exc}") from exc
    try:
        return json.loads(body) if body.strip().startswith("{") else {"raw": body}
    except json.JSONDecodeError:
        return {"raw": body}


def available(host: str = DEFAULT_HOST) -> bool:
    try:
        _request(f"{host}/system_stats", timeout=5)
        return True
    except ComfyUnavailable:
        return False


def submit(workflow: dict, host: str = DEFAULT_HOST) -> str:
    """Workflow'u kuyruğa verir, prompt_id döndürür."""
    result = _request(f"{host}/prompt", data={"prompt": workflow})
    prompt_id = result.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI prompt_id döndürmedi: {result}")
    return str(prompt_id)


def wait(prompt_id: str, host: str = DEFAULT_HOST, timeout_s: float = 300.0, poll_s: float = 2.0) -> dict:
    """Sonucu bekler; history kaydını döndürür."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        history = _request(f"{host}/history/{prompt_id}", timeout=15)
        record = history.get(prompt_id)
        if record:
            return record
        time.sleep(poll_s)
    raise TimeoutError(f"ComfyUI {prompt_id} {timeout_s:.0f}s içinde bitmedi")


def download(record: dict, out_dir: str | Path, host: str = DEFAULT_HOST) -> list[Path]:
    """History kaydındaki çıktıları indirir."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    outputs = (record.get("outputs") or {})
    for node in outputs.values():
        for key in ("images", "gifs", "videos", "audio"):
            for item in node.get(key) or []:
                filename = item.get("filename")
                if not filename:
                    continue
                query = urllib.parse.urlencode({
                    "filename": filename,
                    "subfolder": item.get("subfolder", ""),
                    "type": item.get("type", "output"),
                })
                url = f"{host}/view?{query}"
                target = out / Path(filename).name
                try:
                    with urllib.request.urlopen(url, timeout=60) as response:
                        target.write_bytes(response.read())
                    saved.append(target)
                except (urllib.error.URLError, OSError):
                    continue
    return saved


def render(workflow: dict, out_dir: str | Path, host: str = DEFAULT_HOST,
           timeout_s: float = 300.0) -> list[Path]:
    """Tek çağrıda: gönder → bekle → indir."""
    if not available(host):
        raise ComfyUnavailable(f"ComfyUI kapalı: {host}")
    prompt_id = submit(workflow, host=host)
    record = wait(prompt_id, host=host, timeout_s=timeout_s)
    return download(record, out_dir, host=host)


def fill_template(template_path: str | Path, **params) -> dict:
    """Workflow JSON'unda {{anahtar}} yer tutucularını doldurur."""
    raw = Path(template_path).read_text(encoding="utf-8")
    for key, value in params.items():
        raw = raw.replace("{{" + key + "}}", str(value))
    return json.loads(raw)
