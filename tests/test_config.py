import os
import unittest
from unittest.mock import patch


class SettingsTests(unittest.TestCase):
    def test_mock_mode_is_default_and_fingerprint_redacts_secret(self):
        from bpmn_adapt.config import Settings

        with patch.dict(os.environ, {"ADAPT_LLM_API_KEY": "secret-value"}, clear=True):
            settings = Settings.from_env()
        self.assertEqual("mock", settings.llm_mode)
        self.assertNotIn("secret-value", settings.fingerprint())

    def test_live_mode_requires_api_key(self):
        from bpmn_adapt.config import ConfigurationError, Settings

        with patch.dict(os.environ, {"ADAPT_LLM_MODE": "live"}, clear=True):
            with self.assertRaises(ConfigurationError):
                Settings.from_env()

    def test_domain_contract_serialises_enums_and_paths(self):
        from pathlib import Path
        from bpmn_adapt.domain.models import AdaptationRequest, OperationType

        request = AdaptationRequest(
            request_id="req-1", process_id="p1", source_folder=Path("demo"),
            operation=OperationType.REMOVE, raw_text="remove Task A", target_element="Task A"
        )
        payload = request.to_dict()
        self.assertEqual("REMOVE", payload["operation"])
        self.assertEqual("demo", payload["source_folder"])


if __name__ == "__main__":
    unittest.main()
