from pathlib import Path

p = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\ahos\owner_console.py")
t = p.read_text(encoding="utf-8")

qa = '''def _document_qa(item, result, qa_worker_id):
    """Belge departmanları için kabul: üretilen dosya gerçekten var mı?

    Anlamsal doğruluk iddia edilmez; yalnız üretim kanıtı (dosya + boyut)
    doğrulanır. Dosya yoksa fail-closed kalır.
    """

    from .worker_runtime import QaExecutionResult

    artifacts = tuple(getattr(result, "artifacts", ()) or ())
    verified = [
        path
        for path in artifacts
        if Path(str(path)).is_file() and Path(str(path)).stat().st_size > 0
    ]
    if verified:
        return QaExecutionResult(
            task_id=item.task_id,
            qa_worker_id=qa_worker_id,
            passed=True,
            summary=(
                "belge kabulü: üretilen dosya mevcut ve boş değil "
                f"({len(verified)} dosya); anlamsal doğruluk sahibe aittir"
            ),
        )
    return QaExecutionResult(
        task_id=item.task_id,
        qa_worker_id=qa_worker_id,
        passed=False,
        summary="belge kabulü: üretilmiş dosya yok (fail-closed)",
    )


'''

if "def _document_qa(" not in t:
    marker = "def _unverified_qa(item, result, qa_worker_id):"
    t = t.replace(marker, qa + marker, 1)

t = t.replace("            qa_executor = _unverified_qa", "            qa_executor = _document_qa")
p.write_text(t, encoding="utf-8")
print("document_qa eklendi:", "def _document_qa(" in t)
print("çağrı yeri güncel:", "qa_executor = _document_qa" in t)
