"""Deterministik basit düzenlemeler — model gerektirmeyen %100 başarı sınıfı.

Bazı görevler tam olarak tanımlıdır: "X dosyasının sonuna şu yorumu ekle: ..."
Bu işler için model çağırmak hem yavaş hem gereksiz risklidir. Burada desen
eşleşirse düzenleme **birebir** uygulanır; dosya değişmezse başarısız sayılır.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .targets import mentioned_files

_APPEND_PATTERNS = (
    re.compile(r"sonuna\s+(?:şu|su)?\s*(?:yorumu?|satırı?|satiri?|kodu?)?\s*ekle\s*[:\-]?\s*(?P<text>.+)$", re.IGNORECASE | re.DOTALL),
    re.compile(r"append\s*[:\-]?\s*(?P<text>.+)$", re.IGNORECASE | re.DOTALL),
)
_PREPEND_PATTERNS = (
    re.compile(r"başına\s+(?:şu|su)?\s*(?:yorumu?|satırı?)?\s*ekle\s*[:\-]?\s*(?P<text>.+)$", re.IGNORECASE | re.DOTALL),
)


@dataclass(frozen=True)
class SimpleEdit:
    path: str
    text: str
    mode: str  # "append" | "prepend"


def parse_simple_edit(root: str | Path, objective: str) -> SimpleEdit | None:
    """Görev metni basit bir ekleme ise (dosya, metin, mod) döndürür."""

    base = Path(root)
    files = mentioned_files(objective)
    if not files:
        return None
    target: str | None = None
    for relative in files:
        if (base / relative).is_file():
            target = relative
            break
    if target is None:
        return None

    body = objective.split("\n")[0]
    for mode, patterns in (("append", _APPEND_PATTERNS), ("prepend", _PREPEND_PATTERNS)):
        for pattern in patterns:
            match = pattern.search(body)
            if not match:
                continue
            text = match.group("text").strip().strip('"').strip("'")
            # Yalnızca tek satırlık, kısa eklemeler deterministik yapılır.
            if not text or len(text) > 400:
                continue
            return SimpleEdit(path=target, text=text, mode=mode)
    return None


def apply_simple_edit(root: str | Path, edit: SimpleEdit) -> tuple[bool, str]:
    """Düzenlemeyi uygular; dosya gerçekten değiştiyse True döner."""

    base = Path(root)
    target = base / edit.path
    if not target.is_file():
        return False, f"hedef dosya yok: {edit.path}"

    original = target.read_text(encoding="utf-8", errors="replace")
    if edit.mode == "append":
        if edit.text in original:
            # Idempotent: metin zaten varsa görev başarısızdır değil, no-op başarıdır.
            return True, "metin zaten mevcut (değişiklik gerekmedi)"
        changed = original if original.endswith("\n") or not original else original + "\n"
        changed += edit.text
        if not changed.endswith("\n"):
            changed += "\n"
    else:
        if edit.text in original:
            return True, "metin zaten mevcut (değişiklik gerekmedi)"
        changed = edit.text + "\n" + original

    if changed == original:
        return False, "değişiklik yok"
    target.write_text(changed, encoding="utf-8")
    return True, f"{edit.mode}: {edit.path} (+{len(changed) - len(original)} bayt)"


def make_simple_edit_executor(project_root: str | Path, artifacts_root: str | Path):
    """Basit ekleme görevlerini model olmadan %100 güvenilirlikle uygular."""

    root = Path(project_root)

    def _execute(item, worker_id: str):
        from .worker_runtime import WorkerExecutionResult

        edit = parse_simple_edit(root, item.title)
        if edit is None:
            return WorkerExecutionResult(
                task_id=item.task_id, worker_id=worker_id, success=False,
                summary="basit düzenleme deseni eşleşmedi",
            )
        ok, detail = apply_simple_edit(root, edit)
        evidence = ""
        if ok:
            # Kanıt, izinli artefakt alanında olmalı: QA yalnız orayı okur.
            safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in item.task_id)[:80]
            destination = Path(artifacts_root) / safe
            destination.mkdir(parents=True, exist_ok=True)
            evidence_path = destination / "CHANGES.diff"
            evidence_path.write_text(
                f"--- a/{edit.path}\n+++ b/{edit.path}\n{edit.mode}: {edit.text}\n",
                encoding="utf-8",
            )
            evidence = str(evidence_path)
        return WorkerExecutionResult(
            task_id=item.task_id, worker_id=worker_id, success=ok,
            summary=detail,
            artifacts=(evidence,) if evidence else (),
        )

    return _execute
