"""Var olan bir dosyaya gerçek görev verir ve dosya değişimini kanıtlar.

Kullanım:
    python tools/software_file_task.py --append "def mul(a, b): return a * b"

Ne yapar (sırayla):
 1. Hedef dosyanın önceki SHA-256'sını ve içeriğini kaydeder.
 2. Görevi company-service kuyruğuna yazar (mission_id üretir).
 3. Görevi hedefli olarak sahiplenir (queue.claim_next(mission_id=...)).
 4. queue_drain'in deterministik hızlı yoluyla eklemeyi uygular ve
    **bağımsız geri okuma** ile doğrular (değişmeyen dosya başarı sayılmaz).
 5. Sonucu kuyruğa işler; ardından projenin kendi kabul kapısını çalıştırır
    (tools/check_offline.py + pytest tests).
 6. Kanıtı stdout'a ve runtime/software-file-proof.jsonl dosyasına yazar.

Kural: sayı/iddia yalnız gerçek dosya hash'i ve gerçek komut çıktısıyla verilir.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
RUNTIME = CORE / "runtime"
PROJECT = RUNTIME / "projects" / "pilot-software"
PROOF_LOG = RUNTIME / "software-file-proof.jsonl"
sys.path.insert(0, str(CORE))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(command: list[str], cwd: Path) -> dict:
    started = time.monotonic()
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    return {
        "command": " ".join(command),
        "exit": proc.returncode,
        "seconds": round(time.monotonic() - started, 3),
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default="app/math_utils.py", help="proje içindeki var olan dosya")
    parser.add_argument("--append", default="def mul(a, b): return a * b", help="sonuna eklenecek satır")
    parser.add_argument("--department", default="software")
    args = parser.parse_args(argv)

    from ahos.autonomous_company import PersistentMissionQueue
    from ahos.mission_orchestrator import MissionResult, MissionStatus
    from ahos.owner_console import build_default_console
    from ahos.simple_edits import apply_simple_edit, parse_simple_edit

    target = PROJECT / args.file
    if not target.is_file():
        print(f"HATA: hedef dosya yok: {target}")
        return 2

    before_text = target.read_text(encoding="utf-8", errors="replace")
    before_hash = _sha256(target)
    print(f"önce:  {args.file} sha256={before_hash[:16]}… boyut={target.stat().st_size}")

    if args.append.strip() and args.append.strip() in before_text:
        print("HATA: eklenecek metin dosyada zaten var; kanıt üretilemez (no-op)")
        return 3

    stamp = int(time.time())
    mission_id = f"CMD-{args.department}-file-proof-{stamp}"
    objective = f"{args.file} dosyasının sonuna şu satırı ekle: {args.append}"
    queue = PersistentMissionQueue(RUNTIME / "company-service.db")
    queue.enqueue(
        mission_id=mission_id,
        objective=objective,
        primary_department=args.department,
        max_attempts=1,
        replace_existing=True,
    )
    print(f"görev: {mission_id}")

    console = build_default_console(RUNTIME)
    spec = console.book.get(args.department)
    if spec is None:
        print(f"HATA: departman yok: {args.department}")
        return 2

    owner = "dsh-software-file-proof"
    claimed = queue.claim_next(owner=owner, lease_seconds=900, mission_id=mission_id)
    if claimed is None:
        print("HATA: görev sahiplenilemedi")
        return 4

    started = time.monotonic()
    project = console._project_for_department(args.department)
    project_root = Path(project.work_path or project.path) if project else PROJECT
    edit = parse_simple_edit(project_root, objective)
    if edit is None:
        result = MissionResult(
            mission_id=mission_id,
            objective=objective,
            manager_id=None,
            status=MissionStatus.BLOCKED,
            steps=(),
            reason="basit düzenleme deseni eşleşmedi (hedef dosya bulunamadı)",
        )
        console._record(mission_id, owner, result)
        print("HATA: görev deseni eşleşmedi; görev blocked yazıldı")
        return 5

    ok, detail = apply_simple_edit(project_root, edit)
    after_text = target.read_text(encoding="utf-8", errors="replace")
    after_hash = _sha256(target)

    # Bağımsız geri okuma: dosya gerçekten değişti mi ve beklenen içerik mi?
    if edit.mode == "append":
        expected = before_text if not before_text or before_text.endswith("\n") else before_text + "\n"
        expected += edit.text
        if not expected.endswith("\n"):
            expected += "\n"
    else:
        expected = edit.text + "\n" + before_text
    verified = bool(ok and after_text != before_text and after_text == expected)

    result = MissionResult(
        mission_id=mission_id,
        objective=objective,
        manager_id=None,
        status=MissionStatus.COMPLETED if verified else MissionStatus.BLOCKED,
        steps=(),
        reason=detail if verified else f"simple_edit_delivery_unverified: {detail}",
        qa_worker_id="simple-edit-file-verifier" if verified else None,
    )
    console._record(mission_id, owner, result)
    elapsed = round(time.monotonic() - started, 3)

    # Yönetici zihnine gerçek sonuç geri beslemesi (diğer işçiler ayrı araçla).
    try:
        from ahos.mind_feedback import feedback

        feedback(
            RUNTIME,
            f"{args.department}-manager",
            args.department,
            verified,
            duration_s=elapsed,
            plan_type="simple_edit",
            mission_id=mission_id,
        )
    except Exception as exc:  # noqa: BLE001 - geri besleme kanıtı bozmaz
        print(f"uyarı: geri besleme yazılamadı: {type(exc).__name__}: {exc}")

    stored = queue.get(mission_id)
    status = stored.status.value if stored is not None else "?"

    gate = _run([sys.executable, "tools/check_offline.py"], PROJECT)
    tests = _run([sys.executable, "-m", "pytest", "-q", "--no-header", "tests"], PROJECT)

    proof = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "mission_id": mission_id,
        "department": args.department,
        "project": str(PROJECT),
        "file": args.file,
        "objective": objective,
        "before": {"sha256": before_hash, "bytes": len(before_text.encode())},
        "after": {"sha256": after_hash, "bytes": len(after_text.encode())},
        "changed": after_hash != before_hash,
        "verified_readback": verified,
        "mission_status": status,
        "seconds": elapsed,
        "acceptance_gate": gate,
        "pytest": tests,
    }

    print(f"sonra: {args.file} sha256={after_hash[:16]}… boyut={proof['after']['bytes']}")
    print(f"değişti: {proof['changed']} · geri okuma: {verified} · görev: {status} ({elapsed}s)")
    print(f"kabul kapısı: exit={gate['exit']} · {gate['stdout'].splitlines()[-1] if gate['stdout'] else gate['stderr'][:120]}")
    print(f"pytest: exit={tests['exit']} · {(tests['stdout'].splitlines()[-1] if tests['stdout'] else tests['stderr'][:120])}")

    PROOF_LOG.parent.mkdir(parents=True, exist_ok=True)
    with PROOF_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(proof, ensure_ascii=False) + "\n")

    ok_all = verified and status == "completed" and gate["exit"] == 0 and tests["exit"] == 0
    print("SONUÇ:", "KANIT TAMAM" if ok_all else "KANIT EKSİK")
    print(f"kanıt dosyası: {PROOF_LOG}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
