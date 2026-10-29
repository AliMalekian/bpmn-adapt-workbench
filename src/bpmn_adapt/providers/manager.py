"""Single source of truth for LLM provider configuration and client creation."""
from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
import threading
import time
from typing import Any, Callable

from bpmn_adapt.llm.client import LLMClient, LLMError
from bpmn_adapt.llm.openai_compatible import OpenAICompatibleClient
from bpmn_adapt.llm.um_client import UMLLMClient

logger = logging.getLogger(__name__)


class ProviderManager:
    """Thread-safe manager for LLM provider configuration and client lifecycle."""

    _instances: dict[str, ProviderManager] = {}
    _class_lock = threading.Lock()

    def __new__(cls, config_path: str | Path = "providers.json"):
        normalized = str(Path(config_path).resolve())
        with cls._class_lock:
            if normalized not in cls._instances:
                inst = super().__new__(cls)
                inst._initialized = False
                cls._instances[normalized] = inst
            return cls._instances[normalized]

    def __init__(self, config_path: str | Path = "providers.json"):
        if getattr(self, "_initialized", False):
            return
        self.config_path = Path(config_path)
        self._lock = threading.RLock()
        self._observers: list[Callable[[], None]] = []
        self._fallback_policy: dict[str, Any] = {
            "on_429": True,
            "on_5xx": True,
            "on_timeout": True,
            "on_4xx_non_429": False,
            "max_retries_per_provider": 3,
        }
        self._providers: list[dict[str, Any]] = self._load()
        self._initialized = True

    def _load(self) -> list[dict[str, Any]]:
        with self._lock:
            if not self.config_path.exists():
                example = self.config_path.parent / "providers.example.json"
                if example.exists():
                    try:
                        data = json.loads(example.read_text(encoding="utf-8"))
                        self._fallback_policy = data.get("fallback_policy", self._fallback_policy)
                        return data.get("providers", [])
                    except Exception:
                        pass
                return []

            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                self._fallback_policy = data.get("fallback_policy", self._fallback_policy)
                return data.get("providers", [])
            except Exception as exc:
                logger.error("Failed to load %s: %s", self.config_path, exc)
                return []

    def _save(self) -> None:
        with self._lock:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "providers": self._providers,
                "fallback_policy": self._fallback_policy,
            }
            tmp_path = self.config_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp_path.replace(self.config_path)

    def _notify(self) -> None:
        for callback in list(self._observers):
            try:
                callback()
            except Exception as exc:
                logger.warning("Observer notification error: %s", exc)

    def subscribe(self, callback: Callable[[], None]) -> None:
        with self._lock:
            if callback not in self._observers:
                self._observers.append(callback)

    def unsubscribe(self, callback: Callable[[], None]) -> None:
        with self._lock:
            if callback in self._observers:
                self._observers.remove(callback)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            sorted_providers = sorted(self._providers, key=lambda p: (p.get("priority", 99), p.get("id", "")))
            return copy.deepcopy(sorted_providers)

    def get(self, provider_id: str) -> dict[str, Any] | None:
        with self._lock:
            for p in self._providers:
                if p.get("id") == provider_id:
                    return copy.deepcopy(p)
            return None

    def reorder_priority(self, provider_id: str, new_priority: int) -> None:
        """Move provider to new_priority and cascade-shift other providers to prevent duplicates."""
        with self._lock:
            target = None
            for p in self._providers:
                if p.get("id") == provider_id:
                    target = p
                    break
            if not target:
                raise ValueError(f"Provider '{provider_id}' not found")

            # Collect all other providers sorted by current priority
            others = [p for p in sorted(self._providers, key=lambda x: (int(x.get("priority", 99)), x.get("id", ""))) if p.get("id") != provider_id]

            # 1-based index insertion
            insert_idx = max(0, min(int(new_priority) - 1, len(others)))
            others.insert(insert_idx, target)

            # Reassign clean sequential 1-based priorities
            for rank, p in enumerate(others, start=1):
                p["priority"] = rank

            self._save()
            self._notify()

    def add(self, provider: dict[str, Any]) -> None:
        with self._lock:
            pid = provider.get("id")
            if not pid:
                raise ValueError("Provider configuration must include a unique 'id'")
            if any(p.get("id") == pid for p in self._providers):
                raise ValueError(f"Provider with id '{pid}' already exists")

            desired_priority = int(provider.get("priority", len(self._providers) + 1))
            new_prov = {
                "id": str(pid),
                "name": str(provider.get("name", pid)),
                "type": str(provider.get("type", "openai_compatible")),
                "base_url": str(provider.get("base_url", "")),
                "model": str(provider.get("model", "")),
                "api_key": str(provider.get("api_key", "")),
                "priority": desired_priority,
                "enabled": bool(provider.get("enabled", False)),
            }
            if new_prov["type"] == "um_llm":
                new_prov["server_id"] = int(provider.get("server_id", 1))

            self._providers.append(new_prov)
            self.reorder_priority(pid, desired_priority)

    def update(self, provider_id: str, updates: dict[str, Any]) -> None:
        with self._lock:
            target = None
            for p in self._providers:
                if p.get("id") == provider_id:
                    target = p
                    break
            if not target:
                raise ValueError(f"Provider '{provider_id}' not found")

            updates_copy = dict(updates)
            new_prio = updates_copy.pop("priority", None)
            target.update(updates_copy)

            if new_prio is not None and int(new_prio) != target.get("priority"):
                self.reorder_priority(provider_id, int(new_prio))
            else:
                self._save()
                self._notify()

    def delete(self, provider_id: str) -> None:
        with self._lock:
            orig_len = len(self._providers)
            self._providers = [p for p in self._providers if p.get("id") != provider_id]
            if len(self._providers) != orig_len:
                # Re-index remaining providers sequentially
                sorted_rem = sorted(self._providers, key=lambda x: (int(x.get("priority", 99)), x.get("id", "")))
                for rank, p in enumerate(sorted_rem, start=1):
                    p["priority"] = rank
                self._save()
                self._notify()

    def enable(self, provider_id: str) -> None:
        self.update(provider_id, {"enabled": True})

    def disable(self, provider_id: str) -> None:
        self.update(provider_id, {"enabled": False})

    def set_api_key(self, provider_id: str, api_key: str, enable_if_set: bool = False) -> None:
        updates: dict[str, Any] = {"api_key": api_key.strip()}
        if enable_if_set and api_key.strip():
            updates["enabled"] = True
        self.update(provider_id, updates)

    def update_api_key_runtime(self, provider_id: str, new_api_key: str) -> None:
        """Atomically updates provider API key at runtime and notifies running components."""
        self.set_api_key(provider_id, new_api_key, enable_if_set=True)
        logger.info("Runtime API key updated for provider '%s'", provider_id)

    def enabled_providers(self) -> list[dict[str, Any]]:
        with self._lock:
            enabled = [
                copy.deepcopy(p)
                for p in self._providers
                if p.get("enabled") and p.get("api_key", "").strip()
            ]
            return sorted(enabled, key=lambda p: (p.get("priority", 99), p.get("id", "")))

    def get_fallback_policy(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._fallback_policy)

    def update_fallback_policy(self, updates: dict[str, Any]) -> None:
        with self._lock:
            self._fallback_policy.update(updates)
            self._save()
            self._notify()

    def set_fallback_policy(self, updates: dict[str, Any]) -> None:
        """Alias for update_fallback_policy."""
        self.update_fallback_policy(updates)

    def build_client(self, provider_id: str) -> LLMClient:
        with self._lock:
            p = self.get(provider_id)
            if not p:
                raise ValueError(f"Provider '{provider_id}' not found in configuration")

            ptype = p.get("type", "openai_compatible")
            api_key = p.get("api_key", "").strip()
            base_url = p.get("base_url", "")
            model = p.get("model", "")
            max_retries = int(self._fallback_policy.get("max_retries_per_provider", 3))

            if ptype == "um_llm":
                return UMLLMClient(
                    base_url=base_url or "https://fumllm.um.ac.ir",
                    api_key=api_key,
                    model=model or "gemma4",
                    server_id=int(p.get("server_id", 1)),
                    max_retries=max_retries,
                )

            return OpenAICompatibleClient(
                base_url=base_url,
                api_key=api_key,
                model=model,
                max_retries=max_retries,
                timeout=float(p.get("timeout", 30.0)),
            )

    def test(self, provider_id: str) -> dict[str, Any]:
        with self._lock:
            p = self.get(provider_id)
            if not p:
                return {"provider_id": provider_id, "status": "FAIL", "latency": 0.0, "error": "Provider not found"}

            api_key = p.get("api_key", "").strip()
            if not api_key:
                return {
                    "provider_id": provider_id,
                    "name": p.get("name", provider_id),
                    "model": p.get("model", ""),
                    "status": "FAIL",
                    "latency": 0.0,
                    "error": "API key is empty. Set API key before testing.",
                }

        t0 = time.monotonic()
        try:
            client = self.build_client(provider_id)
            system_prompt = "You are an automated connectivity verification agent."
            user_payload = json.dumps({"action": "ping", "test": "canary"}, ensure_ascii=False)
            res = client.complete(system_prompt, user_payload, schema_name="canary")
            latency = round(time.monotonic() - t0, 3)
            return {
                "provider_id": provider_id,
                "name": p.get("name", provider_id),
                "model": p.get("model", ""),
                "status": "OK",
                "latency": latency,
                "error": None,
                "response": res,
            }
        except Exception as exc:
            latency = round(time.monotonic() - t0, 3)
            return {
                "provider_id": provider_id,
                "name": p.get("name", provider_id),
                "model": p.get("model", ""),
                "status": "FAIL",
                "latency": latency,
                "error": str(exc),
            }

    def test_all(self) -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}
        for p in self.enabled_providers():
            pid = p["id"]
            results[pid] = self.test(pid)
        return results

    def fetch_models(self, provider_id: str) -> list[str]:
        """Fetches active available models from provider's /models endpoint."""
        with self._lock:
            p = self.get(provider_id)
            if not p:
                raise ValueError(f"Provider '{provider_id}' not found")
            ptype = p.get("type", "openai_compatible")
            base_url = p.get("base_url", "").strip().rstrip("/")
            api_key = p.get("api_key", "").strip()

        if ptype == "um_llm":
            return ["gemma4", "gemma3", "gemma3:27b"]

        if not base_url:
            raise ValueError("Base URL is empty")

        url = f"{base_url}/models"
        headers = {"User-Agent": "BPMN-Adapt-Workbench/1.0"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        import urllib.request
        import json
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.load(resp)
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch models from {url}: {exc}") from exc

        raw_list = data.get("data") or data.get("models") or []
        model_ids: list[str] = []
        is_google = "googleapis.com" in base_url.lower()

        if isinstance(raw_list, list):
            for item in raw_list:
                if isinstance(item, dict):
                    mid = item.get("id") or item.get("name") or ""
                elif isinstance(item, str):
                    mid = item
                else:
                    continue
                if not mid:
                    continue
                if is_google and mid.startswith("models/"):
                    mid = mid[len("models/"):]
                model_ids.append(mid)

        if not model_ids and isinstance(data, list):
            model_ids = [str(x) for x in data]

        return sorted(list(set(model_ids)))
