from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Mapping, Protocol

from .visual_pipeline import RenderJob


class RunPodProviderError(RuntimeError):
    pass


class RunPodConfigurationError(RunPodProviderError):
    pass


class RunPodExecutionGateError(RunPodProviderError):
    pass


class RunPodResponseError(RunPodProviderError):
    pass


_ENDPOINT_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True, slots=True)
class RunPodLTX2Config:
    endpoint_id: str
    base_url: str = "https://api.runpod.ai/v2"
    api_key_env: str = "RUNPOD_API_KEY"
    request_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not _ENDPOINT_RE.fullmatch(self.endpoint_id):
            raise ValueError("invalid RunPod endpoint_id")
        parsed = urllib.parse.urlparse(self.base_url)
        if parsed.scheme != "https":
            raise ValueError("RunPod base_url must use https")
        if parsed.hostname != "api.runpod.ai":
            raise ValueError("RunPod base_url host must be api.runpod.ai")
        if not self.api_key_env.strip():
            raise ValueError("api_key_env must not be empty")

    @property
    def endpoint_base(self) -> str:
        return f"{self.base_url.rstrip('/')}/{self.endpoint_id}"

    def api_key(self) -> str:
        return os.getenv(self.api_key_env, "").strip()

    def configured(self) -> bool:
        return bool(self.endpoint_id and self.api_key())


@dataclass(frozen=True, slots=True)
class PaidExecutionApproval:
    owner_approved: bool = False
    execution_enabled: bool = False
    paid_provider_enabled: bool = False

    def require(self) -> None:
        missing: list[str] = []
        if not self.owner_approved:
            missing.append("owner_approved")
        if not self.execution_enabled:
            missing.append("execution_enabled")
        if not self.paid_provider_enabled:
            missing.append("paid_provider_enabled")
        if missing:
            raise RunPodExecutionGateError(
                "RunPod paid execution blocked: " + ", ".join(missing)
            )


class RunPodTransport(Protocol):
    def request_json(
        self,
        method: str,
        url: str,
        *,
        api_key: str,
        payload: Mapping[str, object] | None = None,
        timeout: float = 30.0,
    ) -> object:
        ...


class UrlLibRunPodTransport:
    def request_json(
        self,
        method: str,
        url: str,
        *,
        api_key: str,
        payload: Mapping[str, object] | None = None,
        timeout: float = 30.0,
    ) -> object:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except (urllib.error.URLError, OSError) as exc:
            raise RunPodResponseError(str(exc)) from exc

        if not raw.strip():
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RunPodResponseError(
                f"RunPod returned non-JSON response: {exc}"
            ) from exc


class RunPodLTX2Provider:
    """Guarded RunPod Serverless adapter for the existing LTX-2 worker.

    Network execution is impossible unless the caller explicitly supplies all
    three paid-execution gates. The API key is read from an environment
    variable and is never serialized into job payloads or configuration files.
    """

    def __init__(
        self,
        config: RunPodLTX2Config,
        *,
        transport: RunPodTransport | None = None,
    ) -> None:
        self.config = config
        self.transport = transport or UrlLibRunPodTransport()

    def configuration_summary(self) -> dict[str, object]:
        return {
            "provider_id": "runpod-ltx2",
            "endpoint_id": self.config.endpoint_id,
            "endpoint_base": self.config.endpoint_base,
            "api_key_env": self.config.api_key_env,
            "api_key_present": bool(self.config.api_key()),
            "paid": True,
            "external": True,
        }

    @staticmethod
    def health_payload() -> dict[str, object]:
        return {"input": {"ping": True}}

    @staticmethod
    def bootstrap_payload(*, force_download: bool = False) -> dict[str, object]:
        return {
            "input": {
                "bootstrap_models": True,
                "force_model_download": bool(force_download),
            }
        }

    @staticmethod
    def render_payload(
        job: RenderJob,
        *,
        workflow_api: str = "image_to_video.api.json",
        width: int = 1024,
        height: int = 576,
        fps: int = 24,
        steps: int = 8,
        input_image_base64: str | None = None,
        input_image_url: str | None = None,
        wait: bool = True,
        return_output_base64: bool = False,
        preserve_outputs: bool = False,
    ) -> dict[str, object]:
        if input_image_base64 and input_image_url:
            raise ValueError(
                "use only one of input_image_base64 or input_image_url"
            )
        if width % 32 != 0 or height % 32 != 0:
            raise ValueError("LTX-2 width and height must be divisible by 32")
        if fps <= 0 or steps <= 0:
            raise ValueError("fps and steps must be positive")

        request: dict[str, object] = {
            "workflow_api": workflow_api,
            "positive_prompt": job.positive_prompt,
            "negative_prompt": job.negative_prompt,
            "duration_seconds": job.duration_seconds,
            "fps": fps,
            "steps": steps,
            "seed": job.seed,
            "width": width,
            "height": height,
            "wait": bool(wait),
            "return_output_base64": bool(return_output_base64),
            "preserve_outputs": bool(preserve_outputs),
            "cleanup_inputs": True,
            "cleanup_outputs": not bool(preserve_outputs),
            "client_id": f"ahos-{job.episode_id}-{job.shot_id}",
        }
        if input_image_base64:
            request["input_image_base64"] = input_image_base64
        if input_image_url:
            request["input_image_url"] = input_image_url

        return {"input": request}

    def _require_api_key(self) -> str:
        api_key = self.config.api_key()
        if not api_key:
            raise RunPodConfigurationError(
                f"{self.config.api_key_env} is not configured"
            )
        return api_key

    def _paid_post(
        self,
        path: str,
        payload: Mapping[str, object],
        *,
        approval: PaidExecutionApproval,
    ) -> object:
        approval.require()
        api_key = self._require_api_key()
        return self.transport.request_json(
            "POST",
            self.config.endpoint_base + path,
            api_key=api_key,
            payload=payload,
            timeout=self.config.request_timeout_seconds,
        )

    def ping(
        self,
        *,
        approval: PaidExecutionApproval,
    ) -> object:
        # A Serverless health request can wake a GPU worker, so it is treated
        # as a paid execution even though the worker only performs a health check.
        return self._paid_post(
            "/runsync",
            self.health_payload(),
            approval=approval,
        )

    def bootstrap_models(
        self,
        *,
        approval: PaidExecutionApproval,
        force_download: bool = False,
    ) -> object:
        return self._paid_post(
            "/runsync",
            self.bootstrap_payload(force_download=force_download),
            approval=approval,
        )

    def submit(
        self,
        payload: Mapping[str, object],
        *,
        approval: PaidExecutionApproval,
        synchronous: bool = False,
    ) -> object:
        return self._paid_post(
            "/runsync" if synchronous else "/run",
            payload,
            approval=approval,
        )

    def status(self, job_id: str) -> object:
        api_key = self._require_api_key()
        safe_job_id = urllib.parse.quote(job_id, safe="")
        return self.transport.request_json(
            "GET",
            f"{self.config.endpoint_base}/status/{safe_job_id}",
            api_key=api_key,
            timeout=self.config.request_timeout_seconds,
        )

    def cancel(
        self,
        job_id: str,
        *,
        owner_approved: bool,
    ) -> object:
        if not owner_approved:
            raise RunPodExecutionGateError(
                "owner approval is required to cancel a RunPod job"
            )
        api_key = self._require_api_key()
        safe_job_id = urllib.parse.quote(job_id, safe="")
        return self.transport.request_json(
            "POST",
            f"{self.config.endpoint_base}/cancel/{safe_job_id}",
            api_key=api_key,
            payload={},
            timeout=self.config.request_timeout_seconds,
        )
