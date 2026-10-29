"""Provider-neutral language-model protocol and error types."""
from __future__ import annotations
from typing import Any, Protocol


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    def complete(self, system_prompt: str, user_payload: str, *, schema_name: str) -> dict[str, Any]: ...


class EmbeddingClient(Protocol):
    model_id: str
    def embed(self, text: str) -> tuple[float, ...]: ...

