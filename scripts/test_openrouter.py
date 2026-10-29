import sys
sys.path.insert(0, "src")
from bpmn_adapt.config import Settings
from bpmn_adapt.llm.openai_compatible import OpenAICompatibleClient


s = Settings.load()
print("Mode:", s.llm_mode)
print("Base URL:", s.llm_base_url)
print("Model:", s.llm_model)
print("API Key present:", bool(s.llm_api_key))

try:
    client = OpenAICompatibleClient(
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        model=s.llm_model,
        timeout=15.0
    )


    res = client.complete(
        "You are a BPMN compliance assistant. Return strict JSON with key 'status' as 'APPROVE' or 'REJECT' and 'reason'.",
        '{"process": "Dispatch of goods", "action": "Remove package goods"}',
        schema_name="analyse"
    )
    print("LIVE OPENROUTER RESPONSE:")
    print(res)
except Exception as e:
    print("ERROR CALLING OPENROUTER:", type(e), e)
