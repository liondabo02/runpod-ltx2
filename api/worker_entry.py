import requests
import runpod

from .handler import handle_event


_original_response_json = requests.Response.json


def _safe_response_json(response: requests.Response, *args, **kwargs):
    """Make ComfyUI protocol failures diagnosable without crashing on empty history polls."""
    try:
        return _original_response_json(response, *args, **kwargs)
    except ValueError as exc:
        url = str(getattr(response, "url", ""))
        body = (getattr(response, "text", "") or "").strip()

        # ComfyUI may transiently return an empty 200 while a history item is not ready yet.
        # Treat that like an empty history payload so the handler can keep polling.
        if response.status_code == 200 and "/history/" in url and not body:
            return {}

        method = ""
        request = getattr(response, "request", None)
        if request is not None:
            method = str(getattr(request, "method", "") or "")

        content_type = str(response.headers.get("content-type", "") or "")
        preview = body[:1200] if body else "<empty>"
        raise RuntimeError(
            "ComfyUI returned a non-JSON response: "
            f"method={method or 'unknown'} url={url or '<unknown>'} "
            f"status={response.status_code} content_type={content_type or '<none>'} "
            f"body={preview}"
        ) from exc


# handler.py uses requests.Response.json() in multiple ComfyUI API paths. Installing
# this narrow wrapper gives us deterministic diagnostics and makes empty history
# polling tolerant without retrying POST /prompt (which could duplicate work).
requests.Response.json = _safe_response_json


def worker(event):
    return handle_event(event)


if __name__ == "__main__":
    runpod.serverless.start({"handler": worker})
