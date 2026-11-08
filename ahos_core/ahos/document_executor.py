"""Proje bağlı olmayan departmanlar için belge üretici yürütücü.

Kod projesi olmayan departmanlar (veri, finans, güvenlik, kalite, araştırma,
pazarlama, satış, destek, operasyon, altyapı, holding, stüdyo) için gerçek üretim
yapan tek yol: modelden profesyonel bir belge istemek ve diske yazmak.

Kurallar:
* Model yoksa başarısız döner (sahte başarı yok).
* Çıktı 200 karakterden kısaysa teslim sayılmaz.
* Dosya artefakt olarak kaydedilir; bağımsız ``_document_qa`` bunu doğrular.
"""

from __future__ import annotations

import re
from pathlib import Path

PROMPT_SYSTEM = (
    "Sen bir holding departmanının kıdemli uzmanısın. Türkçe, net ve "
    "profesyonel yazarsın. Yalnızca istenen belgeyi üretirsin."
)

PROMPT_TEMPLATE = (
    "Departman: {department}\n"
    "Görev: {title}\n"
    "İş kimliği: {task_id}\n\n"
    "Bu görev için kısa ve kullanılabilir bir teslim belgesi yaz.\n"
    "Kurallar:\n"
    "- Markdown başlıkları kullan.\n"
    "- 150-200 kelime yeter; boş cümle yerine somut madde ver.\n"
    "- En az 3 uygulanabilir öneri ekle.\n"
    "- Sonuna '## Özet' bölümü koy.\n"
)


def make_document_executor(artifacts_root: str | Path, *, settings=None):
    """Return a WorkerExecutor that writes a real markdown deliverable."""

    root = Path(artifacts_root)

    def _execute(item, worker_id: str):
        from .llm_executor import ModelError, http_transport, load_settings
        from .worker_runtime import WorkerExecutionResult

        active = settings or load_settings()
        if active is None:
            return WorkerExecutionResult(
                task_id=item.task_id,
                worker_id=worker_id,
                success=False,
                summary="belge üretici: model yapılandırılmadı",
            )

        # Uzun yanıt tünelde zaman aşımına düşüyordu: 700 token + 300 sn sınır.
        from dataclasses import replace as _replace

        active = _replace(
            active,
            max_tokens=700,
            timeout_seconds=max(float(active.timeout_seconds), 300.0),
        )

        prompt = PROMPT_TEMPLATE.format(
            department=item.department,
            title=item.title,
            task_id=item.task_id,
        )
        try:
            raw = http_transport(PROMPT_SYSTEM, prompt, active)
        except ModelError as exc:
            return WorkerExecutionResult(
                task_id=item.task_id,
                worker_id=worker_id,
                success=False,
                summary=f"belge üretici model hatası: {exc}",
            )

        text = (raw or "").strip()
        if len(text) < 200:
            return WorkerExecutionResult(
                task_id=item.task_id,
                worker_id=worker_id,
                success=False,
                summary=f"belge üretici: çıktı çok kısa ({len(text)} karakter)",
            )

        safe_task = re.sub(r"[^A-Za-z0-9._-]+", "_", item.task_id).strip("._") or "task"
        destination = root / safe_task
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / "deliverable.md"
        path.write_text(
            f"# {item.title}\n\n"
            f"- Görev: {item.task_id}\n- Departman: {item.department}\n"
            f"- İşçi: {worker_id}\n\n{text}\n",
            encoding="utf-8",
        )

        return WorkerExecutionResult(
            task_id=item.task_id,
            worker_id=worker_id,
            success=True,
            summary=(
                f"belge üretildi ({len(text)} karakter); çıktı: {path.name}"
            ),
            artifacts=(str(path),),
        )

    return _execute
