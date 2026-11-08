import copy
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


def _normalize_runpod_event(event):
    """Translate friendly API aliases into the handler's unambiguous fields.

    The public request format historically used `prompt` for natural-language text,
    while handler.py also uses `prompt` for an inline ComfyUI JSON graph. A plain
    text prompt therefore reached json.loads() and failed with
    `Expecting value: line 1 column 1 (char 0)` before any GPU work began.

    Likewise, `image` is accepted by callers as an HTTP URL, while the handler's
    materializer expects `image_url`/`input_image_url` for remote files.
    """
    normalized = copy.deepcopy(event)
    if not isinstance(normalized, dict):
        return normalized

    req = normalized.get("input")
    if not isinstance(req, dict):
        req = normalized

    prompt_value = req.get("prompt")
    if isinstance(prompt_value, str):
        stripped = prompt_value.strip()
        looks_like_json_graph = stripped.startswith("{") or stripped.startswith("[")
        if not looks_like_json_graph:
            req.setdefault("positive_prompt", prompt_value)
            req.pop("prompt", None)

    image_value = req.get("image")
    if isinstance(image_value, str):
        stripped_image = image_value.strip()
        if stripped_image.startswith(("http://", "https://")):
            req.setdefault("image_url", image_value)

    return normalized


def worker(event):
    return handle_event(_normalize_runpod_event(event))


if __name__ == "__main__":
    runpod.serverless.start({"handler": worker})
