"""Layered, typed, and secret-safe runtime configuration.

Precedence is: explicit overrides > environment > .env > TOML profile >
dataclass defaults.  The module intentionally uses only the Python standard
library so the offline configuration path works before optional dependencies
are installed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import hashlib
import json
import os
from pathlib import Path
import shlex
import tomllib
from typing import Any, Mapping


class ConfigurationError(ValueError):
    """Raised before a run when configuration is inconsistent or unsafe."""


@dataclass(frozen=True)
class CapabilityStatus:
    """Configuration-level readiness; it never claims a live probe passed."""

    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class Settings:
    # LLM/API
    llm_mode: str = "live"
    llm_provider: str = "openai_compatible"
    llm_model: str = "example-model"
    llm_fallback_model: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_fallback_base_url: str = ""
    llm_fallback_api_key: str = ""
    timeout_seconds: float = 60.0
    max_retries: int = 2
    retry_backoff_seconds: float = 1.0
    rate_limit_per_minute: int = 30
    providers: tuple[dict[str, Any], ...] = ()

    # Embeddings and retrieval
    # The no-profile default is deliberately dependency-free. Production and
    # integration profiles explicitly select the neural encoder.
    embedding_provider: str = "hash_test"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_revision: str = "main"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 32
    vector_backend: str = "local"
    vector_path: Path = Path("experiments/vector_index")
    rag_mode: str = "hybrid"
    rag_semantic_weight: float = 0.65
    rag_syntactic_weight: float = 0.35

    # Persistence and artefacts
    database_url: str = "sqlite:///experiments/runtime_bpmn.db"
    output_root: Path = Path("experiments/runs")

    # Agent and temporal planning controls
    max_agent_retries: int = 2
    planner_weight_time: float = 0.4
    planner_weight_budget: float = 0.3
    planner_weight_risk: float = 0.3
    planner_max_states: int = 10_000
    planner_max_depth: int = 100
    planner_timeout_seconds: float = 30.0

    # Workflow engine
    engine_mode: str = "disabled"
    engine_base_url: str = "http://localhost:8080"
    engine_oauth_url: str = ""
    engine_client_id: str = ""
    engine_client_secret: str = ""
    engine_tenant_id: str = "research"
    engine_timeout_seconds: float = 30.0
    engine_max_retries: int = 2

    # Formal checker and evaluation
    formal_mode: str = "disabled"
    external_checker_command: tuple[str, ...] = ()
    external_checker_timeout_seconds: float = 30.0
    evaluation_seed: int = 20260922
    evaluation_repetitions: int = 5

    _ENV_FIELDS = {
        "ADAPT_LLM_MODE": ("llm_mode", str),
        "ADAPT_LLM_PROVIDER": ("llm_provider", str),
        "ADAPT_LLM_MODEL": ("llm_model", str),
        "ADAPT_LLM_FALLBACK_MODEL": ("llm_fallback_model", str),
        "ADAPT_LLM_BASE_URL": ("llm_base_url", str),
        "ADAPT_LLM_API_KEY": ("llm_api_key", str),
        "ADAPT_LLM_FALLBACK_BASE_URL": ("llm_fallback_base_url", str),
        "ADAPT_LLM_FALLBACK_API_KEY": ("llm_fallback_api_key", str),
        "ADAPT_LLM_TIMEOUT_SECONDS": ("timeout_seconds", float),
        "ADAPT_LLM_MAX_RETRIES": ("max_retries", int),
        "ADAPT_LLM_RETRY_BACKOFF_SECONDS": ("retry_backoff_seconds", float),
        "ADAPT_LLM_RATE_LIMIT_REQUESTS_PER_MINUTE": ("rate_limit_per_minute", int),
        "ADAPT_EMBEDDING_PROVIDER": ("embedding_provider", str),
        "ADAPT_EMBEDDING_MODEL": ("embedding_model", str),
        "ADAPT_EMBEDDING_REVISION": ("embedding_revision", str),
        "ADAPT_EMBEDDING_DEVICE": ("embedding_device", str),
        "ADAPT_EMBEDDING_BATCH_SIZE": ("embedding_batch_size", int),
        "ADAPT_VECTOR_BACKEND": ("vector_backend", str),
        "ADAPT_VECTOR_PATH": ("vector_path", Path),
        "ADAPT_DATABASE_URL": ("database_url", str),
        "ADAPT_RAG_MODE": ("rag_mode", str),
        "ADAPT_RAG_SEMANTIC_WEIGHT": ("rag_semantic_weight", float),
        "ADAPT_RAG_SYNTACTIC_WEIGHT": ("rag_syntactic_weight", float),
        "ADAPT_OUTPUT_ROOT": ("output_root", Path),
        "ADAPT_MAX_AGENT_RETRIES": ("max_agent_retries", int),
        "ADAPT_PLANNER_WEIGHT_TIME": ("planner_weight_time", float),
        "ADAPT_PLANNER_WEIGHT_BUDGET": ("planner_weight_budget", float),
        "ADAPT_PLANNER_WEIGHT_RISK": ("planner_weight_risk", float),
        "ADAPT_PLANNER_MAX_STATES": ("planner_max_states", int),
        "ADAPT_PLANNER_MAX_DEPTH": ("planner_max_depth", int),
        "ADAPT_PLANNER_TIMEOUT_SECONDS": ("planner_timeout_seconds", float),
        "ADAPT_ENGINE_MODE": ("engine_mode", str),
        "ADAPT_ENGINE_BASE_URL": ("engine_base_url", str),
        "ADAPT_ENGINE_OAUTH_URL": ("engine_oauth_url", str),
        "ADAPT_ENGINE_CLIENT_ID": ("engine_client_id", str),
        "ADAPT_ENGINE_CLIENT_SECRET": ("engine_client_secret", str),
        "ADAPT_ENGINE_TENANT_ID": ("engine_tenant_id", str),
        "ADAPT_ENGINE_TIMEOUT_SECONDS": ("engine_timeout_seconds", float),
        "ADAPT_ENGINE_MAX_RETRIES": ("engine_max_retries", int),
        "ADAPT_EXTERNAL_CHECKER_COMMAND": ("external_checker_command", "command"),
        "ADAPT_FORMAL_MODE": ("formal_mode", str),
        "ADAPT_EXTERNAL_CHECKER_TIMEOUT_SECONDS": ("external_checker_timeout_seconds", float),
        "ADAPT_EVALUATION_SEED": ("evaluation_seed", int),
        "ADAPT_EVALUATION_REPETITIONS": ("evaluation_repetitions", int),
    }

    _PROFILE_FIELDS = {
        "llm": {
            "mode": "llm_mode", "provider": "llm_provider", "model": "llm_model",
            "fallback_model": "llm_fallback_model",
            "base_url": "llm_base_url", "api_key": "llm_api_key",
            "fallback_base_url": "llm_fallback_base_url",
            "fallback_api_key": "llm_fallback_api_key",
            "timeout_seconds": "timeout_seconds", "max_retries": "max_retries",
            "retry_backoff_seconds": "retry_backoff_seconds",
            "rate_limit_per_minute": "rate_limit_per_minute",
        },
        "embedding": {
            "provider": "embedding_provider", "model": "embedding_model",
            "revision": "embedding_revision", "device": "embedding_device",
            "batch_size": "embedding_batch_size",
        },
        "vector": {"backend": "vector_backend", "path": "vector_path"},
        "database": {"url": "database_url"},
        "rag": {
            "mode": "rag_mode", "semantic_weight": "rag_semantic_weight",
            "syntactic_weight": "rag_syntactic_weight",
        },
        "output": {"root": "output_root"},
        "agents": {"max_retries": "max_agent_retries"},
        "planner": {
            "weight_time": "planner_weight_time", "weight_budget": "planner_weight_budget",
            "weight_risk": "planner_weight_risk", "max_states": "planner_max_states",
            "max_depth": "planner_max_depth", "timeout_seconds": "planner_timeout_seconds",
        },
        "engine": {
            "mode": "engine_mode", "base_url": "engine_base_url",
            "oauth_url": "engine_oauth_url", "client_id": "engine_client_id",
            "client_secret": "engine_client_secret", "tenant_id": "engine_tenant_id",
            "timeout_seconds": "engine_timeout_seconds", "max_retries": "engine_max_retries",
        },
        "formal": {
            "mode": "formal_mode",
            "external_checker_command": "external_checker_command",
            "external_checker_timeout_seconds": "external_checker_timeout_seconds",
        },
        "evaluation": {"seed": "evaluation_seed", "repetitions": "evaluation_repetitions"},
    }

    @classmethod
    def load(
        cls,
        profile: Path | str | None = None,
        *,
        environ: Mapping[str, str] | None = None,
        overrides: Mapping[str, Any] | None = None,
        env_file: Path | str | None = None,
    ) -> "Settings":
        """Load and validate settings using documented precedence."""
        values = {item.name: item.default for item in fields(cls)}

        if profile is not None:
            profile_path = Path(profile)
            if not profile_path.is_file():
                raise ConfigurationError(f"Configuration profile not found: {profile_path}")
            values.update(cls._profile_values(tomllib.loads(profile_path.read_text(encoding="utf-8"))))

        dotenv_path = Path(env_file) if env_file is not None else (Path(".env") if environ is None else None)
        merged_environment: dict[str, str] = {}
        if dotenv_path is not None and dotenv_path.is_file():
            merged_environment.update(cls._read_dotenv(dotenv_path))
        merged_environment.update(dict(os.environ if environ is None else environ))
        values.update(cls._environment_values(merged_environment))

        if overrides:
            unknown = set(overrides) - {item.name for item in fields(cls)}
            if unknown:
                raise ConfigurationError(f"Unknown configuration override(s): {', '.join(sorted(unknown))}")
            values.update(overrides)

        values["llm_mode"] = str(values["llm_mode"]).lower()
        values["rag_mode"] = str(values["rag_mode"]).lower()
        values["vector_backend"] = str(values["vector_backend"]).lower()
        values["engine_mode"] = str(values["engine_mode"]).lower()
        values["formal_mode"] = str(values["formal_mode"]).lower()
        values["output_root"] = Path(values["output_root"])
        values["vector_path"] = Path(values["vector_path"])
        if isinstance(values["external_checker_command"], str):
            values["external_checker_command"] = tuple(shlex.split(values["external_checker_command"]))
        elif isinstance(values["external_checker_command"], list):
            values["external_checker_command"] = tuple(map(str, values["external_checker_command"]))

        if "providers" not in values or not values["providers"]:
            prov_file = Path("providers.json")
            if not prov_file.is_file():
                root_prov = Path(__file__).resolve().parents[2] / "providers.json"
                if root_prov.is_file():
                    prov_file = root_prov
            if prov_file.is_file():
                try:
                    pdata = json.loads(prov_file.read_text(encoding="utf-8"))
                    values["providers"] = tuple(pdata.get("providers", []))
                except Exception:
                    pass
        if isinstance(values.get("providers"), list):
            values["providers"] = tuple(values["providers"])

        result = cls(**values)
        result._validate()
        return result

    @classmethod
    def from_env(cls) -> "Settings":
        """Backward-compatible entry point; respects current os.environ."""
        return cls.load(environ=dict(os.environ))

    @classmethod
    def _profile_values(cls, document: Mapping[str, Any]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        unknown_sections = set(document) - set(cls._PROFILE_FIELDS)
        if unknown_sections:
            raise ConfigurationError(f"Unknown configuration section(s): {', '.join(sorted(unknown_sections))}")
        for section, content in document.items():
            if not isinstance(content, Mapping):
                raise ConfigurationError(f"Configuration section [{section}] must be a table")
            mapping = cls._PROFILE_FIELDS[section]
            unknown = set(content) - set(mapping)
            if unknown:
                raise ConfigurationError(f"Unknown key(s) in [{section}]: {', '.join(sorted(unknown))}")
            for key, value in content.items():
                values[mapping[key]] = value
        return values

    @classmethod
    def _environment_values(cls, environ: Mapping[str, str]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for env_name, (field_name, converter) in cls._ENV_FIELDS.items():
            if env_name not in environ:
                continue
            raw = environ[env_name]
            try:
                if converter == "command":
                    value = tuple(shlex.split(raw))
                else:
                    value = converter(raw)
            except (TypeError, ValueError) as exc:
                raise ConfigurationError(f"Invalid value for {env_name}: {raw!r}") from exc
            result[field_name] = value
        return result

    @staticmethod
    def _read_dotenv(path: Path) -> dict[str, str]:
        values: dict[str, str] = {}
        for number, original in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = original.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            if "=" not in line:
                raise ConfigurationError(f"Invalid .env line {number} in {path}")
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if not key:
                raise ConfigurationError(f"Invalid .env key on line {number} in {path}")
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            values[key] = value
        return values

    def _validate(self) -> None:
        if self.llm_mode not in {"mock", "live"}:
            raise ConfigurationError("ADAPT_LLM_MODE must be mock or live")
        has_enabled_provider = any(
            p.get("enabled") and str(p.get("api_key", "")).strip()
            for p in self.providers
        )
        if self.llm_mode == "live" and not self.llm_api_key and not has_enabled_provider:
            raise ConfigurationError("ADAPT_LLM_API_KEY or enabled provider in providers.json is required in live mode")
        if self.rag_mode not in {"hybrid", "semantic", "syntactic", "none"}:
            raise ConfigurationError("ADAPT_RAG_MODE is invalid")
        if self.vector_backend not in {"local", "pgvector"}:
            raise ConfigurationError("ADAPT_VECTOR_BACKEND must be local or pgvector")
        if self.embedding_provider not in {"hash_test", "sentence_transformers"}:
            raise ConfigurationError("ADAPT_EMBEDDING_PROVIDER must be hash_test or sentence_transformers")
        if self.engine_mode not in {"disabled", "dry_run", "camunda8"}:
            raise ConfigurationError("ADAPT_ENGINE_MODE must be disabled, dry_run, or camunda8")
        if self.engine_mode == "camunda8" and not self.engine_base_url:
            raise ConfigurationError("ADAPT_ENGINE_BASE_URL is required for camunda8 mode")
        if self.formal_mode not in {"disabled", "pm4py"}:
            raise ConfigurationError("ADAPT_FORMAL_MODE must be disabled or pm4py")
        planner_total = self.planner_weight_time + self.planner_weight_budget + self.planner_weight_risk
        if abs(planner_total - 1.0) > 1e-9:
            raise ConfigurationError("Planner time, budget, and risk weights must sum to 1")
        rag_total = self.rag_semantic_weight + self.rag_syntactic_weight
        if abs(rag_total - 1.0) > 1e-9:
            raise ConfigurationError("RAG semantic and syntactic weights must sum to 1")
        positive = {
            "ADAPT_LLM_TIMEOUT_SECONDS": self.timeout_seconds,
            "ADAPT_LLM_RATE_LIMIT_REQUESTS_PER_MINUTE": self.rate_limit_per_minute,
            "ADAPT_EMBEDDING_BATCH_SIZE": self.embedding_batch_size,
            "ADAPT_PLANNER_MAX_STATES": self.planner_max_states,
            "ADAPT_PLANNER_MAX_DEPTH": self.planner_max_depth,
            "ADAPT_PLANNER_TIMEOUT_SECONDS": self.planner_timeout_seconds,
            "ADAPT_EVALUATION_REPETITIONS": self.evaluation_repetitions,
        }
        for name, value in positive.items():
            if value <= 0:
                raise ConfigurationError(f"{name} must be positive")

    def redacted_dict(self) -> dict[str, Any]:
        public = asdict(self)
        for key in ("llm_api_key", "llm_fallback_api_key", "engine_client_secret"):
            public[key] = "<redacted>" if public[key] else ""
        public["output_root"] = str(public["output_root"])
        public["vector_path"] = str(public["vector_path"])
        public["external_checker_command"] = list(public["external_checker_command"])
        return public

    def fingerprint(self) -> str:
        public = self.redacted_dict()
        public.pop("llm_api_key", None)
        public.pop("llm_fallback_api_key", None)
        public.pop("engine_client_secret", None)
        encoded = json.dumps(public, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def validate_capabilities(self) -> tuple[CapabilityStatus, ...]:
        llm = CapabilityStatus(
            "llm", "READY_OFFLINE" if self.llm_mode == "mock" else "CONFIGURED_UNVERIFIED",
            "deterministic mock adapter" if self.llm_mode == "mock" else "live endpoint requires a health probe",
        )
        postgres = self.database_url.startswith(("postgresql://", "postgres://"))
        database = CapabilityStatus(
            "database", "CONFIGURED_UNVERIFIED" if postgres else "READY_OFFLINE",
            "PostgreSQL requires a connection probe" if postgres else "SQLite is local",
        )
        vector = CapabilityStatus(
            "vector_store", "CONFIGURED_UNVERIFIED" if self.vector_backend == "pgvector" else "READY_OFFLINE",
            "pgvector requires a connection/extension probe" if self.vector_backend == "pgvector" else "durable local backend configured",
        )
        if self.engine_mode == "disabled":
            engine = CapabilityStatus("engine", "DISABLED", "workflow engine integration disabled")
        elif self.engine_mode == "dry_run":
            engine = CapabilityStatus("engine", "READY_OFFLINE", "dry-run engine adapter")
        else:
            engine = CapabilityStatus("engine", "CONFIGURED_UNVERIFIED", "Camunda requires a live health probe")
        return (llm, database, vector, engine)
