"""Read bounded local research evidence as untrusted prompt data, never instructions."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
from urllib.parse import urlsplit


def _plain_directory(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink() and not getattr(path, "is_junction", lambda: False)()


def _source(record: object) -> dict | None:
    if not isinstance(record, dict):
        return None
    url = record.get("url")
    if not isinstance(url, str) or len(url) > 2048:
        return None
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
        return None
    return {"url": url, "title": str(record.get("title", ""))[:300],
            "content": str(record.get("content", ""))[:1000]}


def load_research_context(departments_root: Path) -> list[dict]:
    """At most five authenticated artifacts, 128 KiB read, 12K prompt characters.

    A content hash detects accidental/tampered bytes; it does not authenticate the
    publisher or verify claims. Unknown schemas and linked files are ignored.
    Only selected public text fields reach the model, never artifact commands.
    """
    root = departments_root.parent / "research-results"
    if not _plain_directory(root):
        return []
    result: list[dict] = []
    byte_budget = 128 * 1024
    try:
        with os.scandir(root) as entries:
            for index, entry in enumerate(entries):
                if index >= 128 or len(result) >= 5 or byte_budget <= 0:
                    break
                path = Path(entry.path)
                if path.suffix != ".json" or path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                    continue
                try:
                    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                    with os.fdopen(fd, "rb") as handle:
                        info = os.fstat(handle.fileno())
                        if not stat.S_ISREG(info.st_mode) or info.st_size > byte_budget:
                            continue
                        raw = handle.read(byte_budget + 1)
                    byte_budget -= len(raw)
                    if byte_budget < 0:
                        break
                    body = json.loads(raw)
                    if not isinstance(body, dict) or body.get("schema") not in ("ahos.vane-research.v1", "ahos.upstream-result.v1"):
                        continue
                    digest = body.pop("artifact_sha256", None)
                    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                    if digest != hashlib.sha256(canonical.encode()).hexdigest():
                        continue
                    if body["schema"] == "ahos.upstream-result.v1" and (body.get("kind") != "public_search" or body.get("success") is not True or body.get("content_is_untrusted") is not True):
                        continue
                    timestamp = body.get("collected_at", body.get("created_at"))
                    if not isinstance(timestamp, str) or len(timestamp) > 100:
                        continue
                    sources = body.get("sources", [])
                    if not isinstance(sources, list):
                        continue
                    record = {"schema": body["schema"], "artifact_sha256": digest,
                              "collected_at": timestamp, "query": str(body.get("query", ""))[:500],
                              "message": str(body.get("message", ""))[:1200],
                              "sources": [s for value in sources[:3] if (s := _source(value))],
                              "trust": "untrusted_retrieved_content", "claims_verified": False,
                              "execution_authority": False}
                    if len(json.dumps(result + [record], ensure_ascii=False)) <= 12000:
                        result.append(record)
                except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
                    continue
    except OSError:
        return result
    return result
