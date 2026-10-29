from __future__ import annotations

import os
import unittest

from bpmn_adapt.llm.openai_compatible import OpenAICompatibleClient


@unittest.skipUnless(os.environ.get("ADAPT_TEST_LLM_API_KEY"),
                     "pending external resource: live OpenAI-compatible API key")
class LiveLLMTests(unittest.TestCase):
    def test_live_provider_returns_validated_json_object(self):
        client=OpenAICompatibleClient(
            base_url=os.environ.get("ADAPT_TEST_LLM_BASE_URL","https://api.openai.com/v1"),
            api_key=os.environ["ADAPT_TEST_LLM_API_KEY"],
            model=os.environ.get("ADAPT_TEST_LLM_MODEL","gpt-5-mini"),
            timeout=60,max_retries=2,rate_limit_per_minute=10)
        value=client.complete(
            "Return only a JSON object matching the request.",
            '{"required_key":"status","required_value":"ok"}',schema_name="live_contract")
        self.assertEqual(value.get("status"),"ok")


if __name__ == "__main__": unittest.main()
