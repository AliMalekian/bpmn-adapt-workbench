"""Unit verification for UMLLMClient."""
import sys
import time

sys.path.insert(0, "src")
from bpmn_adapt.llm.um_client import UMLLMClient

# 1. JSON extraction tests
j1 = UMLLMClient._extract_json('{"status": "APPROVE"}')
assert j1 == {"status": "APPROVE"}, f"Expected APPROVE, got {j1}"

j2 = UMLLMClient._extract_json("```json\n{\"status\": \"REJECT\"}\n```")
assert j2 == {"status": "REJECT"}, f"Expected REJECT, got {j2}"

j3 = UMLLMClient._extract_json("Prefix notes\n{\"status\": \"ALTERNATIVE\"}\nSuffix text")
assert j3 == {"status": "ALTERNATIVE"}, f"Expected ALTERNATIVE, got {j3}"

try:
    UMLLMClient._extract_json("Plain text with no json")
    assert False, "Should have raised LLMError"
except Exception as exc:
    assert "did not contain valid JSON" in str(exc)

# 2. Rate limit test
t0 = time.monotonic()
UMLLMClient._throttle()
UMLLMClient._throttle()
t1 = time.monotonic()
elapsed = round(t1 - t0, 3)
print(f"RATE_LIMIT_TEST: 2 calls elapsed = {elapsed}s (expected >= 2.1s)")
assert elapsed >= 2.05, f"Elapsed time {elapsed} was less than 2.05s"

print("ALL_UM_CLIENT_UNIT_TESTS_PASSED")
