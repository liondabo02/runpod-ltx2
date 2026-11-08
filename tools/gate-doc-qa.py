from pathlib import Path

p = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\ahos\owner_console.py")
t = p.read_text(encoding="utf-8")

old = "            qa_executor = _unverified_qa"
new = (
    '            import os as _os\n'
    '            _doc_qa_on = _os.environ.get("AHOS_DOCUMENT_QA", "0").strip().lower() in {"1", "true", "yes"}\n'
    "            qa_executor = _document_qa if _doc_qa_on else _unverified_qa"
)
if "AHOS_DOCUMENT_QA" not in t:
    t = t.replace(old, new, 1)
    p.write_text(t, encoding="utf-8")
    print("belge kapısı bayrağa bağlandı")
else:
    print("bayrak zaten var")
