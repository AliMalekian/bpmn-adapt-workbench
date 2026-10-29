"""OpenAI-compatible JSON-over-HTTP adapter with multi-provider fallback and bounded retries."""
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
from urllib.request import Request, urlopen

from .client import LLMError

logger = logging.getLogger(__name__)


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        fallback_model: str | None = None,
        fallback_base_url: str | None = None,
        fallback_api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 5,
        backoff: float = 2.0,
        rate_limit_per_minute: int = 30,
        opener=urlopen,
        sleeper=time.sleep,
        clock=time.monotonic,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.model = model
        self.fallback_model = fallback_model or os.getenv("ADAPT_LLM_FALLBACK_MODEL")
        self.fallback_base_url = (fallback_base_url or os.getenv("ADAPT_LLM_FALLBACK_BASE_URL", "")).rstrip("/")
        self.fallback_api_key = (fallback_api_key or os.getenv("ADAPT_LLM_FALLBACK_API_KEY", "")).strip()
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self.minimum_interval = 60.0 / max(1, rate_limit_per_minute)
        self._opener, self._sleeper, self._clock = opener, sleeper, clock
        self._last_request: float | None = None
        self._lock = threading.Lock()
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0

    def complete(self, system_prompt: str, user_payload: str, *, schema_name: str) -> dict[str, Any]:
        providers = [
            {
                "model": self.model,
                "base_url": self.base_url,
                "api_key": self.api_key,
            }
        ]
        if self.fallback_model:
            providers.append({
                "model": self.fallback_model,
                "base_url": self.fallback_base_url or self.base_url,
                "api_key": self.fallback_api_key or self.api_key,
            })

        last_error: Exception | None = None

        for provider in providers:
            current_model = self._normalize_model(provider["model"], provider["base_url"])
            current_base_url = provider["base_url"]
            current_api_key = provider["api_key"]

            for attempt in range(self.max_retries + 1):
                t_start = self._clock()
                try:
                    self._throttle()
                    req_dict: dict[str, Any] = {
                        "model": current_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_payload},
                        ],
                    }
                    if schema_name != "canary":
                        req_dict["response_format"] = {"type": "json_object"}
                    body = json.dumps(req_dict).encode("utf-8")

                    request = Request(
                        f"{current_base_url}/chat/completions",
                        data=body,
                        headers={
                            "Authorization": f"Bearer {current_api_key}",
                            "Content-Type": "application/json",
                            "User-Agent": "BPMN-Adapt-Workbench/1.0",
                            "HTTP-Referer": "https://github.com/bpmn-adapt/workbench",
                            "X-Title": "BPMN Runtime Adaptation Workbench",
                        },
                        method="POST",
                    )

                    with self._opener(request, timeout=self.timeout) as response:
                        payload = json.load(response)

                    if isinstance(payload, dict) and "error" in payload and "choices" not in payload:
                        err_msg = payload["error"].get("message", str(payload["error"]))
                        code = 429 if "rate" in err_msg.lower() else 500
                        raise HTTPError(request.full_url, code, err_msg, {}, None)

                    content = payload["choices"][0]["message"]["content"]
                    parsed = self._extract_json(content)
                    if not isinstance(parsed, dict):
                        raise LLMError(f"{schema_name} response was not a valid JSON object: {content}")

                    usage = payload.get("usage") if isinstance(payload, dict) else {}
                    if not isinstance(usage, dict):
                        usage = {}
                    prompt_tokens = usage.get("prompt_tokens") or max(1, len(system_prompt + user_payload) // 4)
                    completion_tokens = usage.get("completion_tokens") or max(1, len(content) // 4)
                    total_tokens = usage.get("total_tokens") or (prompt_tokens + completion_tokens)

                    self.total_prompt_tokens += prompt_tokens
                    self.total_completion_tokens += completion_tokens
                    self.total_tokens += total_tokens

                    latency = self._clock() - t_start
                    provider_name = "aistudio" if "googleapis.com" in current_base_url else ("groq" if "groq.com" in current_base_url else "other")
                    self._log_llm_call(
                        provider=provider_name,
                        model=current_model,
                        schema_name=schema_name,
                        attempt=attempt,
                        system_prompt=system_prompt,
                        user_payload=user_payload,
                        response=parsed,
                        latency_seconds=latency,
                        status="SUCCESS",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                    )
                    return parsed

                except HTTPError as exc:
                    latency = self._clock() - t_start
                    last_error = exc
                    provider_name = "aistudio" if "googleapis.com" in current_base_url else ("groq" if "groq.com" in current_base_url else "other")
                    self._log_llm_call(
                        provider=provider_name,
                        model=current_model,
                        schema_name=schema_name,
                        attempt=attempt,
                        system_prompt=system_prompt,
                        user_payload=user_payload,
                        response={"error_type": "HTTPError", "code": exc.code, "reason": str(exc.reason)},
                        latency_seconds=latency,
                        status="FAILED",
                    )
                    # Fatal client errors: 4xx EXCEPT 429
                    if 400 <= exc.code < 500 and exc.code != 429:
                        logger.error(f"Non-retryable HTTP {exc.code} error from {current_base_url}: {exc.reason}")
                        raise LLMError(f"HTTP {exc.code} client error from {current_base_url}: {exc.reason}") from exc

                    # Retryable: 429 or 5xx
                    if attempt < self.max_retries:
                        delay = self.backoff * (2 ** attempt)
                        retry_after = exc.headers.get("Retry-After") if hasattr(exc, "headers") and exc.headers else None
                        if retry_after:
                            try:
                                ra_val = float(retry_after)
                                if ra_val > 60.0:
                                    logger.warning(f"Retry-After {ra_val:.1f}s exceeds maximum backoff window (60s). Failing fast to allow provider failover.")
                                    break
                                delay = max(delay, ra_val)
                            except ValueError:
                                pass
                        logger.warning(
                            f"Model {current_model} returned HTTP {exc.code} (attempt {attempt + 1}/{self.max_retries + 1}). "
                            f"Retrying in {delay:.1f}s..."
                        )
                        self._sleeper(delay)
                    else:
                        logger.warning(f"Model {current_model} exhausted {self.max_retries} retries on HTTP {exc.code}.")
                        break

                except (URLError, TimeoutError, socket.timeout, ConnectionError) as exc:
                    latency = self._clock() - t_start
                    last_error = exc
                    provider_name = "aistudio" if "googleapis.com" in current_base_url else ("groq" if "groq.com" in current_base_url else "other")
                    self._log_llm_call(
                        provider=provider_name,
                        model=current_model,
                        schema_name=schema_name,
                        attempt=attempt,
                        system_prompt=system_prompt,
                        user_payload=user_payload,
                        response={"error_type": type(exc).__name__, "error_message": str(exc)},
                        latency_seconds=latency,
                        status="FAILED",
                    )
                    if attempt < self.max_retries:
                        delay = self.backoff * (2 ** attempt)
                        logger.warning(
                            f"Model {current_model} network/timeout error {type(exc).__name__} "
                            f"(attempt {attempt + 1}/{self.max_retries + 1}). Retrying in {delay:.1f}s..."
                        )
                        self._sleeper(delay)
                    else:
                        logger.warning(f"Model {current_model} exhausted {self.max_retries} retries on timeout/network error.")
                        break

                except (json.JSONDecodeError, KeyError, LLMError, Exception) as exc:
                    latency = self._clock() - t_start
                    last_error = exc
                    provider_name = "aistudio" if "googleapis.com" in current_base_url else ("groq" if "groq.com" in current_base_url else "other")
                    self._log_llm_call(
                        provider=provider_name,
                        model=current_model,
                        schema_name=schema_name,
                        attempt=attempt,
                        system_prompt=system_prompt,
                        user_payload=user_payload,
                        response={"error_type": type(exc).__name__, "error_message": str(exc)},
                        latency_seconds=latency,
                        status="FAILED",
                    )
                    if attempt < self.max_retries:
                        delay = self.backoff * (2 ** attempt)
                        logger.warning(
                            f"Model {current_model} parsing error {type(exc).__name__} "
                            f"(attempt {attempt + 1}/{self.max_retries + 1}). Retrying in {delay:.1f}s..."
                        )
                        self._sleeper(delay)
                    else:
                        break

        raise LLMError(
            f"All LLM attempts failed across providers. Last error: {type(last_error).__name__} ({last_error})"
        ) from last_error

    def _log_llm_call(
        self,
        *,
        provider: str = "aistudio",
        model: str,
        schema_name: str,
        attempt: int,
        system_prompt: str,
        user_payload: str,
        response: Any,
        latency_seconds: float,
        status: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        log_dir = Path("experiments/live_evaluation_v4") if Path("experiments/live_evaluation_v4").exists() else Path("live_evaluation_v3")
        log_path = log_dir / "llm_calls.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "status": status,
                        "provider": provider,
                        "model": model,
                        "schema_name": schema_name,
                        "attempt": attempt,
                        "system_prompt": system_prompt,
                        "user_payload": user_payload,
                        "response": response,
                        "latency_seconds": round(latency_seconds, 4),
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(text[first_brace : last_brace + 1])
            except Exception:
                pass
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
            return {"result": parsed}
        except Exception:
            pass

        # Smart Auto-Repair for truncated JSON:
        t_core = text[first_brace:] if first_brace != -1 else text
        for suffix in ['"}]}', '"}]}]}', '"}}}', '"}]', '"}', '}]}', '}}', '}']:
            try:
                parsed = json.loads(t_core + suffix)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        pos = max(t_core.rfind(","), t_core.rfind("}"), t_core.rfind("]"))
        if pos > 0:
            clean_head = t_core[:pos].rstrip(",")
            for suffix in ["}]}", "}]", "}}", "}", "]"]:
                try:
                    parsed = json.loads(clean_head + suffix)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass

        return {"raw_response": text}

    def _throttle(self) -> None:
        with self._lock:
            now = self._clock()
            if self._last_request is not None:
                delay = self.minimum_interval - (now - self._last_request)
                if delay > 0:
                    self._sleeper(delay)
                    now += delay
            self._last_request = now

    @staticmethod
    def _normalize_model(model: str, base_url: str) -> str:
        b = base_url.lower()
        if "googleapis.com" in b:
            # Google's OpenAI-compatible endpoint expects model name without 'models/' prefix
            if model.startswith("models/"):
                return model[len("models/"):]
            return model
        return model
