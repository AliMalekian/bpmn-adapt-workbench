"""Authenticated, rate-limited, retry-bounded HTTP transport for Camunda 8."""
from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any

from .contracts import EngineAdapterError


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    payload: dict[str, Any]
    headers: dict[str, str]


class CamundaHttpTransport:
    """Small httpx wrapper that never logs tokens or response secrets."""

    RETRYABLE = {429, 502, 503, 504}

    def __init__(self, base_url: str, *, oauth_url: str = "", client_id: str = "",
                 client_secret: str = "", timeout: float = 30.0, max_retries: int = 2,
                 rate_limit_per_minute: int = 60, verify_tls: bool = True,
                 sleeper=time.sleep):
        import httpx
        self.base_url = base_url.rstrip("/")
        self.oauth_url, self.client_id, self._client_secret = oauth_url, client_id, client_secret
        self.timeout, self.max_retries = timeout, max_retries
        self.minimum_interval = 60.0 / max(1, rate_limit_per_minute)
        self.sleeper, self._last_request, self._lock = sleeper, 0.0, threading.Lock()
        self.client = httpx.Client(timeout=timeout, verify=verify_tls)
        self._token: str | None = None

    def request(self, method, path, *, json=None, files=None, headers=None,
                idempotency_key=None):
        import httpx
        request_headers = {"Accept": "application/json", **(headers or {})}
        token = self._access_token()
        if token: request_headers["Authorization"] = f"Bearer {token}"
        if idempotency_key: request_headers["Idempotency-Key"] = idempotency_key
        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                response = self.client.request(method, self.base_url + path, json=json,
                                               files=files, headers=request_headers)
            except httpx.TimeoutException as exc:
                if attempt == self.max_retries:
                    raise EngineAdapterError("Camunda request timed out", code="ENGINE_TIMEOUT",
                                             retryable=True) from exc
                self.sleeper(2 ** attempt); continue
            if response.status_code in {401, 403}:
                raise EngineAdapterError("Camunda authentication/authorization failed",
                                         code="ENGINE_AUTH", retryable=False)
            if response.status_code in self.RETRYABLE and attempt < self.max_retries:
                self.sleeper(2 ** attempt); continue
            try: payload = response.json() if response.content else {}
            except ValueError: payload = {"detail": response.text[:2000]}
            if response.status_code >= 400:
                raise EngineAdapterError(str(payload.get("detail", "Camunda request failed")),
                                         code="ENGINE_HTTP_ERROR",
                                         retryable=response.status_code in self.RETRYABLE)
            return HttpResponse(response.status_code, payload, dict(response.headers))
        raise AssertionError("unreachable")

    def _access_token(self):
        if not self.oauth_url: return None
        if self._token: return self._token
        response = self.client.post(self.oauth_url, data={"grant_type": "client_credentials",
            "client_id": self.client_id, "client_secret": self._client_secret})
        if response.status_code >= 400:
            raise EngineAdapterError("OAuth token request failed", code="ENGINE_AUTH")
        self._token = str(response.json()["access_token"])
        return self._token

    def _throttle(self):
        with self._lock:
            now = time.monotonic(); delay = self.minimum_interval - (now - self._last_request)
            if delay > 0: self.sleeper(delay)
            self._last_request = time.monotonic()

    def close(self): self.client.close()
