from __future__ import annotations

import json
import unittest

from bpmn_adapt.llm.openai_compatible import OpenAICompatibleClient


class Response:
    def __init__(self, value): self.value=value
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self): return json.dumps(self.value).encode()


class OpenAICompatibleContractTests(unittest.TestCase):
    def test_request_is_json_object_mode_and_rate_limit_is_enforced(self):
        requests=[]; sleeps=[]; times=iter((10.0,10.5))
        def opener(request,timeout):
            requests.append((request,timeout))
            return Response({"choices":[{"message":{"content":json.dumps({"ok":True})}}]})
        client=OpenAICompatibleClient(base_url="https://llm.example/v1",api_key="secret",
            model="model",timeout=7,max_retries=0,rate_limit_per_minute=60,
            opener=opener,sleeper=sleeps.append,clock=lambda:next(times))
        self.assertEqual(client.complete("system","{}",schema_name="test"),{"ok":True})
        self.assertEqual(client.complete("system","{}",schema_name="test"),{"ok":True})
        body=json.loads(requests[0][0].data)
        self.assertEqual(body["response_format"],{"type":"json_object"})
        self.assertEqual(requests[0][1],7)
        self.assertEqual(sleeps,[.5])
        self.assertNotIn("secret",repr(body))


if __name__ == "__main__": unittest.main()
