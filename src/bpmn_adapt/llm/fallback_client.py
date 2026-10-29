"""Multi-provider Fallback LLM Client that wraps prioritized providers and provides resilient fallback."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import socket
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError

from .client import LLMClient, LLMError

logger = logging.getLogger(__name__)


class FallbackLLMClient(LLMClient):
    """Wraps multiple LLM clients in priority order with automatic fallback on failure."""

    def __init__(
        self,
        providers: list[dict[str, Any]],
        clients: list[Any],
        *,
        log_path: Path | str = "live_evaluation_v3/llm_calls.jsonl",
        manager: Any = None,
    ):
        if len(providers) != len(clients):
            raise ValueError("providers and clients lists must have the same length")
        if not clients:
            raise ValueError("At least one enabled client is required for FallbackLLMClient")

        self.providers = providers
        self.clients = clients
        self.log_path = Path(log_path)
        self.manager = manager
        self.disabled_providers: set[str] = set()
        self._lock = threading.Lock()
        self.call_counts: dict[str, int] = {p.get("id", f"p_{i}"): 0 for i, p in enumerate(providers)}
        self.total_calls = 0

        # Expose attributes from primary provider for backwards compatibility
        primary = providers[0]
        self.model = primary.get("model", getattr(clients[0], "model", ""))
        self.base_url = primary.get("base_url", getattr(clients[0], "base_url", ""))
        self.provider_id = primary.get("id", "primary")

    def _sync_provider_keys(self) -> None:
        """Reads providers.json dynamically before calls to pick up runtime API key updates."""
        try:
            from bpmn_adapt.providers.manager import ProviderManager
            mgr = self.manager or ProviderManager()
            for prov, client in zip(self.providers, self.clients):
                pid = prov.get("id")
                if pid:
                    p_info = mgr.get(pid)
                    if p_info:
                        latest_key = p_info.get("api_key", "").strip()
                        current_key = getattr(client, "api_key", "")
                        if latest_key and latest_key != current_key:
                            client.api_key = latest_key
                            prov["api_key"] = latest_key
                            if pid in self.disabled_providers:
                                logger.info("Re-enabling provider '%s' after runtime API key update.", pid)
                                self.disabled_providers.discard(pid)
        except Exception as exc:
            logger.debug("Failed to sync provider keys dynamically: %s", exc)

    @property
    def fallback_ratio(self) -> float:
        if self.total_calls == 0 or len(self.providers) <= 1:
            return 0.0
        primary_id = self.providers[0].get("id", "primary")
        primary_calls = self.call_counts.get(primary_id, 0)
        fallback_calls = self.total_calls - primary_calls
        return fallback_calls / max(1, self.total_calls)

    @classmethod
    def from_provider_manager(
        cls,
        manager,
        *,
        log_path: Path | str = "live_evaluation_v3/llm_calls.jsonl",
    ) -> FallbackLLMClient:
        enabled = manager.enabled_providers()
        if not enabled:
            raise ValueError("No enabled providers with API keys found in ProviderManager")
        clients = [manager.build_client(p["id"]) for p in enabled]
        return cls(enabled, clients, log_path=log_path, manager=manager)

    def complete(self, system_prompt: str, user_payload: str, *, schema_name: str, **kwargs) -> dict[str, Any]:
        self._sync_provider_keys()
        errors: list[str] = []
        for i, (prov, client) in enumerate(zip(self.providers, self.clients)):
            prov_id = prov.get("id", f"p_{i}")
            if prov_id in self.disabled_providers:
                logger.info("Provider '%s' is session-disabled due to rate limiting. Skipping.", prov_id)
                continue

            model = prov.get("model", getattr(client, "model", "unknown"))
            server_id = prov.get("server_id", 1)
            t_start = time.monotonic()
            try:
                logger.info(
                    "FallbackLLMClient calling provider %s (index=%d, model=%s)",
                    prov_id, i, model,
                )
                result = client.complete(system_prompt, user_payload, schema_name=schema_name, **kwargs)
                latency = time.monotonic() - t_start

                with self._lock:
                    self.call_counts[prov_id] = self.call_counts.get(prov_id, 0) + 1
                    self.total_calls += 1

                self._log_attempt(
                    provider_id=prov_id,
                    model=model,
                    server_id=server_id,
                    status="SUCCESS",
                    latency=latency,
                    attempt_index=i,
                )
                return result

            except Exception as exc:
                latency = time.monotonic() - t_start
                status_code = getattr(exc, "code", None)
                is_recoverable = False

                is_rate_limited = False
                wait_s = 60.0
                if (isinstance(exc, HTTPError) and exc.code == 429) or (status_code == 429):
                    is_rate_limited = True
                    is_recoverable = True
                    ra = getattr(exc, "headers", {}).get("Retry-After") if hasattr(exc, "headers") and exc.headers else None
                    if ra:
                        try:
                            wait_s = float(ra)
                        except ValueError:
                            wait_s = 60.0
                elif "429" in str(exc) or "rate limit" in str(exc).lower() or "exceeds maximum backoff window" in str(exc).lower():
                    is_rate_limited = True
                    is_recoverable = True
                elif isinstance(exc, (TimeoutError, URLError, socket.timeout)):
                    is_recoverable = True
                elif isinstance(exc, HTTPError) or status_code is not None:
                    code = status_code or getattr(exc, "code", 500)
                    if code >= 500:
                        is_recoverable = True
                    elif code in (401, 403, 404):
                        is_recoverable = (i + 1 < len(self.clients))
                elif isinstance(exc, LLMError):
                    is_recoverable = True
                else:
                    is_recoverable = (i + 1 < len(self.clients))

                if is_rate_limited and wait_s >= 60.0:
                    self.disabled_providers.add(prov_id)
                    self._log_rate_limit(prov_id, wait_s)
                    logger.warning("Provider '%s' disabled for session due to hard rate limit (Retry-After: %ss)", prov_id, wait_s)
                elif isinstance(exc, (TimeoutError, URLError, socket.timeout)) or "timed out" in str(exc).lower():
                    self.disabled_providers.add(prov_id)
                    logger.warning("Provider '%s' disabled for session due to unreachable network/timeout.", prov_id)

                err_msg = f"Provider '{prov_id}' (index {i}) failed: {type(exc).__name__}: {exc}"
                logger.warning(err_msg)
                errors.append(err_msg)

                self._log_attempt(
                    provider_id=prov_id,
                    model=model,
                    server_id=server_id,
                    status=f"FAILED ({type(exc).__name__})",
                    latency=latency,
                    attempt_index=i,
                    error=str(exc),
                )

                if not is_recoverable and i + 1 == len(self.clients):
                    raise exc

        raise LLMError(f"All {len(self.clients)} providers in fallback chain failed: {'; '.join(errors)}")

    def _log_attempt(
        self,
        provider_id: str,
        model: str,
        server_id: int,
        status: str,
        latency: float,
        attempt_index: int,
        error: str = "",
    ) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "fallback_client_attempt",
                "provider_id": provider_id,
                "model": model,
                "server_id": server_id,
                "status": status,
                "latency_seconds": round(latency, 4),
                "attempt_index": attempt_index,
                "error": error,
            }
            with self._lock:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as log_err:
            logger.debug("Failed to log fallback attempt: %s", log_err)

    def _log_rate_limit(self, provider_id: str, retry_after_s: float) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "status": "RATE_LIMITED",
                "provider": provider_id,
                "retry_after_s": round(retry_after_s, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            with self._lock:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as log_err:
            logger.debug("Failed to log rate limit entry: %s", log_err)
