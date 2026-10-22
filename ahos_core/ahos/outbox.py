"""Import patch proposals produced by the cloud worker.

The VM keeps working while the PC is off: it writes one JSON proposal per task
into an outbox. This module validates those proposals against the real project,
applies them to a scratch copy, runs verification and only then promotes them.
Anything that fails is reverted and reported — the cloud never writes directly
to the product.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Iterable

from .llm_executor import ModelEdit, ModelError

MAX_EDITS = 3


def load_proposals(directory: str | Path) -> list[dict]:
    base = Path(directory)
    if not base.is_dir():
        return []
    records: list[dict] = []
    for path in sorted(base.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        payload["_file"] = str(path)
        records.append(payload)
    return records


def validate_proposal(record: dict, root: str | Path) -> tuple[list[ModelEdit], list[str]]:
    """Return (edits, problems). Problems are human readable reasons."""

    base = Path(root).resolve()
    problems: list[str] = []
    edits: list[ModelEdit] = []
    raw_edits = record.get("edits")
    if not isinstance(raw_edits, list):
        return [], ["edits listesi yok"]
    for item in raw_edits[:MAX_EDITS]:
        if not isinstance(item, dict):
            problems.append("düzenleme nesnesi değil")
            continue
        path = str(item.get("path") or "").strip().replace("\\", "/")
        if not path:
            problems.append("yol boş")
            continue
        candidate = (base / path).resolve()
        if candidate != base and base not in candidate.parents:
            problems.append(f"proje dışı yol reddedildi: {path}")
            continue
        find = item.get("find")
        replace = item.get("replace")
        content = item.get("content")
        if isinstance(find, str) and find and isinstance(replace, str):
            edits.append(ModelEdit(path=path, find=find, replace=replace))
        elif isinstance(content, str) and content:
            edits.append(ModelEdit(path=path, content=content))
        else:
            problems.append(f"geçersiz düzenleme: {path}")
    return edits, problems


class _Reverter:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.originals: dict[str, str | None] = {}

    def remember(self, edits: Iterable[ModelEdit]) -> None:
        for edit in edits:
            target = self.root / edit.path
            self.originals[edit.path] = (
                target.read_text(encoding="utf-8", errors="replace")
                if target.exists()
                else None
            )

    def revert(self) -> None:
        for path, original in self.originals.items():
            target = self.root / path
            if original is None:
                target.unlink(missing_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(original, encoding="utf-8")


def apply_proposal(
    record: dict,
    root: str | Path,
    verify: Callable[[Path], tuple[bool, str]] | None = None,
) -> dict:
    """Apply one proposal to the project; revert when validation fails."""

    base = Path(root)
    edits, problems = validate_proposal(record, base)
    if problems:
        return {"status": "rejected", "reason": "; ".join(problems), "files": []}
    if not edits:
        return {"status": "rejected", "reason": "uygulanabilir düzenleme yok", "files": []}

    reverter = _Reverter(base)
    reverter.remember(edits)
    applied: list[str] = []
    try:
        for edit in edits:
            edit.apply(base)
            applied.append(edit.path)
    except ModelError as exc:
        reverter.revert()
        return {"status": "rejected", "reason": str(exc), "files": []}

    if verify is not None:
        ok, detail = verify(base)
        if not ok:
            reverter.revert()
            return {"status": "rejected", "reason": f"doğrulama: {detail}", "files": []}
    return {"status": "applied", "reason": "", "files": applied}


def command_verify(command: str) -> Callable[[Path], tuple[bool, str]]:
    """Verification adapter that runs a shell command inside the project."""

    def _run(root: Path) -> tuple[bool, str]:
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=300,
                encoding="utf-8",
                errors="replace",
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return False, f"{type(exc).__name__}: {exc}"
        if completed.returncode != 0:
            tail = (completed.stdout or completed.stderr or "").strip()[-300:]
            return False, f"çıkış {completed.returncode}: {tail}"
        return True, "geçti"

    return _run


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(
            "kullanım: python -m ahos.outbox --dir <outbox> --root <proje> "
            "[--verify \"komut\"] [--report <jsonl>]"
        )
        return 2
    directory = ""
    root = ""
    verify_command = ""
    report = ""
    index = 0
    while index < len(args):
        key = args[index]
        value = args[index + 1] if index + 1 < len(args) else ""
        if key == "--dir":
            directory = value
        elif key == "--root":
            root = value
        elif key == "--verify":
            verify_command = value
        elif key == "--report":
            report = value
        index += 2

    if not directory or not root:
        print("--dir ve --root zorunlu")
        return 2

    verify = command_verify(verify_command) if verify_command else None
    results: list[dict] = []
    for record in load_proposals(directory):
        outcome = apply_proposal(record, root, verify)
        outcome["task"] = record.get("task", "")
        outcome["id"] = record.get("id", "")
        results.append(outcome)
        print(f"[{outcome['status']}] {outcome['task'][:60]} · {outcome['reason'][:90]}")

    if report:
        with open(report, "a", encoding="utf-8") as handle:
            for row in results:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    applied = sum(1 for row in results if row["status"] == "applied")
    print(f"\nuygulanan: {applied}/{len(results)}")
    return 0 if applied else 1


if __name__ == "__main__":
    raise SystemExit(main())
