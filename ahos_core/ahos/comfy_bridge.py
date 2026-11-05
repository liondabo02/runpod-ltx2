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
                basename = Path(filename).name
                if not basename or basename in {".", ".."}:
                    continue
                original = out / basename
                # ComfyUI often reuses output names across jobs. Never overwrite
                # a previous render or count a half-downloaded/empty file.
                for index in range(1000):
                    target = (original if index == 0 else
                              out / f"{original.stem}_{index}{original.suffix}")
                    try:
                        with target.open("xb") as handle:
                            with urllib.request.urlopen(url, timeout=60) as response:
                                import shutil
                                shutil.copyfileobj(response, handle, length=1024 * 1024)
                        if target.stat().st_size == 0:
                            target.unlink(missing_ok=True)
                            break
                        saved.append(target)
                        break
                    except FileExistsError:
                        continue
                    except (urllib.error.URLError, OSError):
                        target.unlink(missing_ok=True)
                        break
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
    import re

    path = Path(template_path)
    if not path.is_file() and not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    values = {"seed": 0, "frames": 1, "width": 512, "height": 512, **params}
    for key in ("seed", "frames", "width", "height"):
        values[key] = int(values[key])
        if values[key] < (0 if key == "seed" else 1):
            raise ValueError(f"Geçersiz {key}")
    def expand(value):
        if isinstance(value, dict):
            return {k: expand(v) for k, v in value.items()}
        if isinstance(value, list):
            return [expand(v) for v in value]
        if isinstance(value, str):
            match = re.fullmatch(r"\{\{(\w+)\}\}", value)
            if match:
                return values[match.group(1)]
            return re.sub(r"\{\{(\w+)\}\}", lambda m: str(values[m.group(1)]), value)
        return value
    result = expand(json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(result, dict) or not result:
        raise ValueError("Workflow boş veya nesne değil")
    return result
