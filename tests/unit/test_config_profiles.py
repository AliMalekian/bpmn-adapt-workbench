"""Behavioral tests for layered, secret-safe runtime configuration."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import tomllib
import unittest

from bpmn_adapt.config import ConfigurationError, Settings


class ConfigurationProfileTests(unittest.TestCase):
    def test_packaging_metadata_is_parseable_and_declares_complete_offline_stack(self) -> None:
        """A duplicate TOML key would make every clean installation fail."""
        root = Path(__file__).resolve().parents[2]
        document = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        dependencies = "\n".join(document["project"]["dependencies"])
        self.assertIn("sentence-transformers", dependencies)
        self.assertIn("pm4py", dependencies)
        self.assertIn("lxml", dependencies)

    def test_example_environment_selects_neural_embeddings(self) -> None:
        """A stale hash provider would contradict the defense configuration."""
        root = Path(__file__).resolve().parents[2]
        values = Settings._read_dotenv(root / ".env.example")
        self.assertEqual(values["ADAPT_EMBEDDING_PROVIDER"], "sentence_transformers")
        self.assertEqual(values["ADAPT_VECTOR_BACKEND"], "local")

    def test_cli_overrides_environment_which_overrides_profile(self) -> None:
        """A wrong precedence order would silently run a different model."""
        with TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.toml"
            profile.write_text(
                '[llm]\nmode="live"\nmodel="profile-model"\napi_key="profile-secret"\n'
                '[database]\nurl="sqlite:///profile.db"\n', encoding="utf-8")
            settings = Settings.load(profile, environ={
                "ADAPT_LLM_MODEL": "environment-model",
                "ADAPT_LLM_API_KEY": "environment-secret",
            }, overrides={"llm_model": "cli-model"})
        self.assertEqual(settings.llm_mode, "live")
        self.assertEqual(settings.llm_model, "cli-model")
        self.assertEqual(settings.llm_api_key, "environment-secret")
        self.assertEqual(settings.database_url, "sqlite:///profile.db")

    def test_redacted_configuration_and_fingerprint_never_expose_secret(self) -> None:
        """Removing redaction would leak a credential into run evidence."""
        first = Settings(llm_api_key="first-secret")
        second = Settings(llm_api_key="different-secret")
        rendered = json.dumps(first.redacted_dict(), sort_keys=True)
        self.assertNotIn("first-secret", rendered)
        self.assertEqual(first.redacted_dict()["llm_api_key"], "<redacted>")
        self.assertEqual(first.fingerprint(), second.fingerprint())

    def test_dotenv_is_loaded_without_overwriting_explicit_environment(self) -> None:
        """A missing dotenv loader would make the documented local setup inert."""
        with TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                '# research profile\nADAPT_LLM_MODE=mock\nADAPT_LLM_MODEL=dotenv-model\n'
                'ADAPT_DATABASE_URL="sqlite:///dotenv.db"\nADAPT_OUTPUT_ROOT=dotenv-runs\n',
                encoding="utf-8")
            settings = Settings.load(
                environ={"ADAPT_LLM_MODEL": "explicit-model"}, env_file=env_file)
        self.assertEqual(settings.llm_mode, "mock")
        self.assertEqual(settings.llm_model, "explicit-model")
        self.assertEqual(settings.database_url, "sqlite:///dotenv.db")
        self.assertEqual(settings.output_root, Path("dotenv-runs"))

    def test_live_mode_requires_key_after_all_layers_are_merged(self) -> None:
        """Validation before merging could accept an unusable live profile."""
        with TemporaryDirectory() as directory:
            profile = Path(directory) / "live.toml"
            profile.write_text('[llm]\nmode="live"\n', encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationError, "ADAPT_LLM_API_KEY"):
                Settings.load(profile, environ={})

    def test_capability_report_distinguishes_ready_and_missing_configuration(self) -> None:
        """Live gates must be reported as blocked rather than falsely passed."""
        offline = Settings()
        live = Settings(llm_mode="live", llm_api_key="secret",
            database_url="postgresql://research@localhost/bpmn",
            vector_backend="pgvector", engine_mode="camunda8",
            engine_base_url="http://localhost:8080")
        offline_status = {item.name: item for item in offline.validate_capabilities()}
        live_status = {item.name: item for item in live.validate_capabilities()}
        self.assertEqual(offline_status["llm"].status, "READY_OFFLINE")
        self.assertEqual(offline_status["database"].status, "READY_OFFLINE")
        self.assertEqual(offline_status["engine"].status, "DISABLED")
        self.assertEqual(live_status["llm"].status, "CONFIGURED_UNVERIFIED")
        self.assertEqual(live_status["database"].status, "CONFIGURED_UNVERIFIED")
        self.assertEqual(live_status["vector_store"].status, "CONFIGURED_UNVERIFIED")
        self.assertEqual(live_status["engine"].status, "CONFIGURED_UNVERIFIED")

    def test_invalid_weights_and_modes_are_rejected(self) -> None:
        """Invalid experiment settings must fail before a run is created."""
        with self.assertRaisesRegex(ConfigurationError, "sum to 1"):
            Settings.load(environ={
                "ADAPT_PLANNER_WEIGHT_TIME": "0.8",
                "ADAPT_PLANNER_WEIGHT_BUDGET": "0.8",
                "ADAPT_PLANNER_WEIGHT_RISK": "0.8",
            })
        with self.assertRaisesRegex(ConfigurationError, "ADAPT_VECTOR_BACKEND"):
            Settings.load(environ={"ADAPT_VECTOR_BACKEND": "unknown"})
        with self.assertRaisesRegex(ConfigurationError, "ADAPT_EMBEDDING_PROVIDER"):
            Settings.load(environ={"ADAPT_EMBEDDING_PROVIDER": "hashing-by-accident"})

    def test_hash_encoder_is_explicitly_test_only_and_profiles_select_intentionally(self) -> None:
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(Settings().embedding_provider, "hash_test")
        self.assertEqual(Settings.load(root / "config/offline.toml", environ={}).embedding_provider, "hash_test")
        self.assertEqual(Settings.load(root / "config/default.toml", environ={}).embedding_provider, "sentence_transformers")


if __name__ == "__main__":
    unittest.main()
