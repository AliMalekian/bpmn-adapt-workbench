"""UM LLM (Ferdowsi University of Mashhad) custom adapter with strict rate limiting and retries."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import socket
import ssl
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen, build_opener, HTTPSHandler

from .client import LLMError

logger = logging.getLogger(__name__)


class UMLLMClient:
    """Adapter for UM LLM query_unified endpoint with global rate limiting."""

    _global_lock = threading.Lock()
    _global_last_request = 0.0
    _min_interval = 2.1  # 2.0s mandatory interval + 100ms margin

    def __init__(
        self,
        *,
        base_url: str = "https://fumllm.um.ac.ir",
        api_key: str = "",
        model: str = "gemma4",
        server_id: int = 1,
        timeout: float = 180.0,
        max_retries: int = 5,
        backoff: float = 2.0,
        log_path: str | Path = "live_evaluation_v3/llm_calls.jsonl",
        request_delay_seconds: float | None = None,
        opener=None,
        sleeper=time.sleep,
        clock=time.monotonic,
    ):
        if request_delay_seconds is not None:
            type(self)._min_interval = max(0.0, float(request_delay_seconds))
        cleaned_url = (base_url or "").strip().rstrip("/")
        for suffix in ("/docs", "/docs/", "/docs2", "/docs2/", "/llm/query_unified"):
            if cleaned_url.endswith(suffix):
                cleaned_url = cleaned_url[:-len(suffix)].rstrip("/")
        if not cleaned_url:
            cleaned_url = "https://172.20.8.152"
        # If url is fumllm.um.ac.ir or http, upgrade to https://172.20.8.152
        if "fumllm.um.ac.ir" in cleaned_url:
            cleaned_url = cleaned_url.replace("http://fumllm.um.ac.ir", "https://172.20.8.152").replace("https://fumllm.um.ac.ir", "https://172.20.8.152")
        self.base_url = cleaned_url
        self.api_key = api_key.strip()
        self.model = model
        self.server_id = int(server_id)
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self.log_path = Path(log_path)
        self.endpoint = f"{self.base_url}/llm/query_unified"
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0

        if opener is None:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            opener = build_opener(HTTPSHandler(context=ctx)).open
        self._opener, self._sleeper, self._clock = opener, sleeper, clock

    @classmethod
    def _throttle(cls, sleeper=time.sleep, clock=time.monotonic) -> None:
        with cls._global_lock:
            now = clock()
            elapsed = now - cls._global_last_request
            if elapsed < cls._min_interval:
                wait_time = cls._min_interval - elapsed
                sleeper(wait_time)
                now = clock()
            cls._global_last_request = clock()

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidate = text[first_brace : last_brace + 1]
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        # Smart Auto-Repair for truncated JSON:
        # Step A: Try closing dangling strings/arrays/objects
        t_core = text[first_brace:] if first_brace != -1 else text
        for suffix in ['"}]}', '"}]}]}', '"}}}', '"}]', '"}', '}]}', '}}', '}']:
            try:
                parsed = json.loads(t_core + suffix)
                if isinstance(parsed, dict):
                    logger.info("Successfully self-healed truncated JSON with suffix %r", suffix)
                    return parsed
            except Exception:
                pass

        # Step B: Trim dangling incomplete key/value after last comma or closing delimiter
        pos = max(t_core.rfind(","), t_core.rfind("}"), t_core.rfind("]"))
        if pos > 0:
            clean_head = t_core[:pos].rstrip(",")
            for suffix in ["}]}", "}]", "}}", "}", "]"]:
                try:
                    parsed = json.loads(clean_head + suffix)
                    if isinstance(parsed, dict):
                        logger.info("Successfully self-healed truncated JSON by trimming trailing key and adding %r", suffix)
                        return parsed
                except Exception:
                    pass

        raise LLMError(f"UM LLM response did not contain valid JSON: {text[:500]!r}")

    def complete(self, system_prompt: str, user_payload: str, *, schema_name: str) -> dict[str, Any]:
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "BPMN-Adapt-Workbench/1.0",
        }

        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            t_start = self._clock()
            self._throttle(sleeper=self._sleeper, clock=self._clock)

            # If previous attempt failed with invalid/truncated JSON, provide feedback to LLM
            current_payload = user_payload
            if attempt > 0 and isinstance(last_error, (LLMError, json.JSONDecodeError)):
                current_payload = (
                    f"{user_payload}\n\n"
                    "CRITICAL CORRECTION NOTICE: Your previous output was truncated or not valid JSON. "
                    "Please respond with ONLY a complete, valid JSON object without markdown fences, "
                    "and keep 'xml_fragment': null to avoid token exhaustion."
                )

            body_dict = {
                "query": current_payload,
                "system_prompt": system_prompt,
                "server_id": self.server_id,
            }
            body = json.dumps(body_dict, ensure_ascii=False).encode("utf-8")
            try:
                request = Request(self.endpoint, data=body, headers=headers, method="POST")
                with self._opener(request, timeout=self.timeout) as resp:
                    resp_data = json.load(resp)

                raw_text = resp_data.get("response", "")
                if not raw_text and isinstance(resp_data, dict):
                    raw_text = json.dumps(resp_data)

                parsed = self._extract_json(raw_text)
                latency = self._clock() - t_start

                usage = resp_data.get("usage") if isinstance(resp_data, dict) else {}
                if not isinstance(usage, dict):
                    usage = {}
                prompt_tokens = usage.get("prompt_tokens") or max(1, len(system_prompt + user_payload) // 4)
                completion_tokens = usage.get("completion_tokens") or max(1, len(raw_text) // 4)
                total_tokens = usage.get("total_tokens") or (prompt_tokens + completion_tokens)

                self.total_prompt_tokens += prompt_tokens
                self.total_completion_tokens += completion_tokens
                self.total_tokens += total_tokens

                self._log_call(
                    status="SUCCESS",
                    schema_name=schema_name,
                    attempt=attempt,
                    system_prompt=system_prompt,
                    user_payload=user_payload,
                    response=parsed,
                    latency_seconds=latency,
                    raw_response=raw_text,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )
                return parsed

            except HTTPError as exc:
                latency = self._clock() - t_start
                last_error = exc
                err_body = ""
                try:
                    err_body = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    pass

                self._log_call(
                    status="FAILED",
                    schema_name=schema_name,
                    attempt=attempt,
                    system_prompt=system_prompt,
                    user_payload=user_payload,
                    response={"error_type": "HTTPError", "code": exc.code, "reason": str(exc.reason), "body": err_body},
                    latency_seconds=latency,
                )

                # UM LLM rate violation (HTTP 401 with wait)
                if exc.code == 401 and "wait" in err_body.lower():
                    logger.warning("UM LLM rate limit encountered (401 rate violation). Backing off 2.5s...")
                    self._sleeper(2.5)
                    continue

                # Retryable: 429 or 5xx
                if exc.code == 429 or 500 <= exc.code < 600:
                    if attempt < self.max_retries:
                        delay = self.backoff * (2 ** attempt)
                        logger.warning(
                            "UM LLM HTTP %d error (attempt %d/%d). Retrying in %.1fs...",
                            exc.code, attempt + 1, self.max_retries + 1, delay
                        )
                        self._sleeper(delay)
                        continue
                    break

                # Non-retryable client error (4xx)
                logger.error("Non-retryable HTTP %d error from UM LLM: %s", exc.code, exc.reason)
                raise LLMError(f"HTTP {exc.code} error from UM LLM: {exc.reason} ({err_body[:200]})") from exc

            except (URLError, TimeoutError, socket.timeout, ConnectionError, json.JSONDecodeError, LLMError) as exc:
                latency = self._clock() - t_start
                last_error = exc
                self._log_call(
                    status="FAILED",
                    schema_name=schema_name,
                    attempt=attempt,
                    system_prompt=system_prompt,
                    user_payload=user_payload,
                    response={"error_type": type(exc).__name__, "error_message": str(exc)},
                    latency_seconds=latency,
                )
                if attempt < self.max_retries:
                    delay = self.backoff * (2 ** attempt)
                    logger.warning(
                        "UM LLM %s (attempt %d/%d). Retrying in %.1fs...",
                        type(exc).__name__, attempt + 1, self.max_retries + 1, delay
                    )
                    self._sleeper(delay)
                    continue
                break

        raise LLMError(f"All UM LLM attempts failed. Last error: {type(last_error).__name__} ({last_error})")

    def _log_call(
        self,
        *,
        status: str,
        schema_name: str,
        attempt: int,
        system_prompt: str,
        user_payload: str,
        response: Any,
        latency_seconds: float,
        raw_response: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "provider": f"um-llm{self.server_id}-{self.model}",
            "model": self.model,
            "server_id": self.server_id,
            "schema_name": schema_name,
            "attempt": attempt,
            "system_prompt": system_prompt,
            "user_payload": user_payload,
            "response": response,
            "latency_seconds": round(latency_seconds, 4),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        if raw_response is not None:
            record["raw_response"] = raw_response[:2000]

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
