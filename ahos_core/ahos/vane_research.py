"""Bounded Vane research client; retrieved content never grants execution authority."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from http.client import HTTPException
import ipaddress
import json
import os
from pathlib import Path
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from uuid import UUID


class VaneResearchError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise VaneResearchError("Vane redirect refused")


class VaneResearchClient:
    def __init__(self, endpoint: str = "http://127.0.0.1:3000", *, timeout: float = 120,
                 max_bytes: int = 2_000_000):
        parsed = urlsplit(endpoint)
        try:
            local = parsed.hostname == "localhost" or ipaddress.ip_address(parsed.hostname or "").is_loopback
        except ValueError:
            local = False
        if (parsed.scheme != "http" or not local or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
            raise ValueError("Vane endpoint must be an HTTP loopback origin")
        if not 0 < timeout <= 300 or not 1 <= max_bytes <= 8_000_000:
            raise ValueError("invalid Vane request bounds")
        self.endpoint = endpoint.rstrip("/")
        self.timeout, self.max_bytes = timeout, max_bytes
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def _json(self, path: str, payload: dict | None = None) -> dict:
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(self.endpoint + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                raw = response.read(self.max_bytes + 1)
            if len(raw) > self.max_bytes:
                raise VaneResearchError("Vane response exceeds size limit")
            result = json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            raise VaneResearchError(f"Vane HTTP {exc.code}") from None
        except (URLError, TimeoutError, OSError, UnicodeError, json.JSONDecodeError, HTTPException):
            raise VaneResearchError("Vane unavailable or returned invalid JSON") from None
        if not isinstance(result, dict):
            raise VaneResearchError("Vane returned an invalid response object")
        return result

    def providers(self) -> tuple[dict, ...]:
        result = self._json("/api/providers").get("providers")
        if not isinstance(result, list) or any(not isinstance(p, dict) for p in result):
            raise VaneResearchError("Vane provider list is invalid")
        # Return only public identifiers, never a provider's credentials/configuration.
        return tuple({"id": p.get("id"), "name": p.get("name"),
                      "chatModels": self._models(p, "chatModels"),
                      "embeddingModels": self._models(p, "embeddingModels")} for p in result)

    @staticmethod
    def _models(provider: dict, field: str) -> list[dict]:
        models = provider.get(field, [])
        if not isinstance(models, list):
            raise VaneResearchError("Vane model list is invalid")
        return [{"name": m.get("name"), "key": m.get("key")} for m in models if isinstance(m, dict)]

    def search(self, query: str, *, provider_id: str, chat_model: str, embedding_model: str,
               allow_external: bool = False, local_ollama_confirmed: bool = False,
               sources: tuple[str, ...] = ("web",), mode: str = "balanced") -> dict:
        if not allow_external:
            raise ValueError("research requires explicit external search authorization")
        if not local_ollama_confirmed:
            raise ValueError("confirm this Vane Ollama provider uses a local, unbilled endpoint")
        UUID(provider_id)
        if not isinstance(query, str) or not query.strip() or len(query) > 16_000:
            raise ValueError("invalid research query")
        if mode not in ("speed", "balanced", "quality") or not sources or not set(sources) <= {"web", "academic", "discussions"}:
            raise ValueError("invalid research options")
        provider = next((p for p in self.providers() if p["id"] == provider_id), None)
        if provider is None or str(provider["name"]).casefold() != "ollama":
            raise ValueError("only the explicitly selected Ollama provider is permitted")
        for key, field in ((chat_model, "chatModels"), (embedding_model, "embeddingModels")):
            if not key or not any(m["key"] == key for m in provider[field]):
                raise ValueError("selected Ollama model is unavailable; no fallback permitted")
        payload = {"chatModel": {"providerId": provider_id, "key": chat_model},
                   "embeddingModel": {"providerId": provider_id, "key": embedding_model},
                   "optimizationMode": mode, "sources": list(sources), "query": query,
                   "history": [], "stream": False}
        result = self._json("/api/search", payload)
        message, records = result.get("message"), result.get("sources")
        if not isinstance(message, str) or not message.strip() or not isinstance(records, list):
            raise VaneResearchError("Vane search result is invalid")
        evidence = []
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("metadata"), dict):
                raise VaneResearchError("Vane source is invalid")
            metadata = record["metadata"]
            url, title, content = metadata.get("url"), metadata.get("title", ""), record.get("pageContent", record.get("content", ""))
            if not all(isinstance(v, str) for v in (url, title, content)):
                raise VaneResearchError("Vane source fields are invalid")
            parsed = urlsplit(url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
                raise VaneResearchError("Vane source URL is invalid")
            evidence.append({"url": url, "title": title, "content": content,
                             "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                             "trust": "untrusted_retrieved_content"})
        return {"schema": "ahos.vane-research.v1", "collected_at": datetime.now(timezone.utc).isoformat(),
                "endpoint": self.endpoint, "query": query, "provider_id": provider_id,
                "chat_model": chat_model, "embedding_model": embedding_model,
                "optimization_mode": mode, "search_sources": list(sources), "message": message,
                "sources": evidence, "status": "research_result_requires_review",
                "execution_authority": False, "local_ollama_confirmed": True}


def save_research(path: Path, result: dict) -> None:
    """Atomically save a research artifact with a deterministic content hash."""
    body = dict(result)
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    body["artifact_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".vane-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(body, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:3000")
    parser.add_argument("--timeout", type=float, default=120)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("providers")
    search = sub.add_parser("search")
    search.add_argument("--query", required=True)
    search.add_argument("--provider-id", required=True)
    search.add_argument("--chat-model", required=True)
    search.add_argument("--embedding-model", required=True)
    search.add_argument("--output", type=Path, required=True)
    search.add_argument("--allow-external", action="store_true")
    search.add_argument("--local-ollama-confirmed", action="store_true")
    search.add_argument("--mode", choices=("speed", "balanced", "quality"), default="balanced")
    search.add_argument("--source", choices=("web", "academic", "discussions"), action="append")
    args = parser.parse_args(argv)
    try:
        client = VaneResearchClient(args.endpoint, timeout=args.timeout)
        if args.command == "providers":
            print(json.dumps({"providers": client.providers()}, ensure_ascii=True))
        else:
            result = client.search(args.query, provider_id=args.provider_id, chat_model=args.chat_model,
                                   embedding_model=args.embedding_model, allow_external=args.allow_external,
                                   local_ollama_confirmed=args.local_ollama_confirmed,
                                   sources=tuple(args.source or ["web"]), mode=args.mode)
            save_research(args.output, result)
            print(json.dumps({"status": result["status"], "artifact": str(args.output),
                              "source_count": len(result["sources"])}, ensure_ascii=True))
        return 0
    except (ValueError, VaneResearchError):
        # Provider error bodies and query content are deliberately not printed.
        print(json.dumps({"status": "blocked", "reason": "Vane request/configuration failed; check local service and selected models"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
