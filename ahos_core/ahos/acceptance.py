"""Verify pre-enrolled acceptance hashes without modifying trust records.

Baseline provisioning belongs to an independent, pre-execution enrollment
step. This checker cannot approve, repair or create a baseline.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MAX_GATE_BYTES = 1024 * 1024
MAX_BASELINE_BYTES = 1024 * 1024

def gate_path(root: str | Path) -> Path:
    return Path(root) / 'tools' / 'check_offline.py'

def trusted_gate(root: str | Path, baseline_path: str | Path) -> tuple[bool, str, str | None]:
    root = Path(root).resolve()
    gate = gate_path(root)
    baseline = Path(baseline_path)
    try:
        # A candidate-controlled symlink must not redirect the acceptance file.
        if gate.is_symlink() or gate.parent.is_symlink() or not gate.is_file():
            return False, 'kabul testi yok veya güvenli dosya değil', None
        gate.resolve().relative_to(root)
        if gate.stat().st_size > MAX_GATE_BYTES:
            return False, 'kabul testi boyut sınırını aşıyor', None
        if baseline.is_symlink() or not baseline.is_file():
            # Dogrulama ASLA guven kaydi olusturmaz: yetkilendirme isi
            # `enroll_gate()` ile, gorev baslamadan ONCE yapilir.
            return False, 'önceden yetkilendirilmiş kabul kaydı yok', None
        if baseline.stat().st_size > MAX_BASELINE_BYTES:
            return False, 'kabul kaydı boyut sınırını aşıyor', None
        raw = baseline.read_bytes()
        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate key')
                result[key] = value
            return result
        entries = json.loads(raw, object_pairs_hook=unique_pairs)
        if not isinstance(entries, dict) or not entries or any(
            not isinstance(k, str) or not isinstance(v, str)
            or re.fullmatch(r'[0-9a-f]{64}', v) is None
            for k, v in entries.items()
        ):
            return False, 'kabul kaydı şeması geçersiz', None
        expected = entries.get(str(gate.resolve()).lower())
        if expected is None:
            # Onceden yetkilendirilmemis proje icin dogrulama sirasinda kayit
            # URETILMEZ; aksi halde isci kendi kabul testini onaylayabilirdi.
            return False, 'bu proje için önceden yetkilendirilmiş kabul yok', None
        with gate.open('rb') as handle:
            content = handle.read(MAX_GATE_BYTES + 1)
        if len(content) > MAX_GATE_BYTES:
            return False, 'kabul testi boyut sınırını aşıyor', None
        digest = hashlib.sha256(content).hexdigest()
        if digest != expected:
            return False, 'kabul tanımı değiştirilmiş: hash uyuşmuyor', digest
        if baseline.read_bytes() != raw:
            return False, 'kabul kaydı denetim sırasında değişti', digest
        return True, 'önceden sabitlenmiş kabul tanımı değişmemiş', digest
    except (OSError, ValueError, UnicodeError):
        return False, 'kabul kaydı veya testi okunamadı/geçersiz', None

def enroll_gate(root, baseline_path):
    """Pin the acceptance gate on first sight; later runs stay hash-checked.

    Enrollment is intentionally minimal: it refuses symlinks and oversized
    files, records the absolute gate path and its SHA-256, and writes the
    baseline atomically. A later change to the gate no longer matches the pin.
    """
    root = Path(root).resolve()
    gate = gate_path(root)
    baseline = Path(baseline_path)
    try:
        if gate.is_symlink() or gate.parent.is_symlink() or not gate.is_file():
            return False, "kabul testi yok veya güvenli dosya değil"
        gate.resolve().relative_to(root)
        if gate.stat().st_size > MAX_GATE_BYTES:
            return False, "kabul testi boyut sınırını aşıyor"
        digest = hashlib.sha256(gate.read_bytes()).hexdigest()
        entries = {}
        if baseline.is_file() and not baseline.is_symlink():
            try:
                entries = json.loads(baseline.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                entries = {}
        if not isinstance(entries, dict):
            entries = {}
        entries[str(gate.resolve()).lower()] = digest
        baseline.parent.mkdir(parents=True, exist_ok=True)
        temporary = baseline.with_suffix(".tmp")
        temporary.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        temporary.replace(baseline)
        return True, "kabul testi sabitlendi"
    except (OSError, ValueError):
        return False, "kabul kaydı yazılamadı"


def check_offline(project_root: str | Path, *, python: str | None = None) -> tuple[bool, str]:
    """Run only the project's own pytest suite after its gate has been enrolled.

    This does not execute candidate-controlled check_offline.py: that file is
    checked separately by trusted_gate() before project_qa invokes this helper.
    """
    root = Path(project_root).resolve()
    gate = gate_path(root)
    if gate.is_symlink() or gate.parent.is_symlink() or not gate.is_file():
        return False, "kabul testi yok (tools/check_offline.py)"
    if not (root / "tests").is_dir() or (root / "tests").is_symlink():
        return False, "kabul testi yok (tests/)"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        result = subprocess.run(
            [python or sys.executable, "-m", "pytest", "-q", "--no-header", "tests"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return False, "0 passed / 1 failed; kabul testi zaman aşımı (120s)"
    except OSError as exc:
        return False, f"0 passed / 1 failed; kabul testi başlatılamadı: {exc}"

    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    lines = output.splitlines()
    # Pytest's final line carries summary counts; collection errors also fail.
    summary = next(
        (line for line in reversed(lines) if re.search(
            r"\b\d+\s+(?:passed|failed|errors?)\b", line
        )),
        "",
    )
    counts = {
        key: sum(int(count) for count, kind in re.findall(
            r"\b(\d+)\s+(passed|failed|errors?)\b", summary
        ) if kind == key)
        for key in ("passed", "failed", "error", "errors")
    }
    passed = counts["passed"]
    failed = counts["failed"] + counts["error"] + counts["errors"]
    ok = result.returncode == 0 and passed > 0 and failed == 0
    if not ok and failed == 0:
        failed = 1  # Includes collection failures and 'no tests ran'.
    detail = f"{passed} passed / {failed} failed"
    if not ok:
        error_start = next(
            (i for i, line in enumerate(lines) if re.search(
                r"^=+\s+(?:FAILURES|ERRORS)\s+=+$", line
            )),
            0,
        )
        excerpt = lines[error_start:error_start + 20]
        if excerpt:
            detail += "\n" + "\n".join(excerpt)
        else:
            detail += "\npytest çıktı üretmedi"
    return ok, detail
