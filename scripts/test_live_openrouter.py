import os
import time
import json
from pathlib import Path
from bpmn_adapt.config import Settings
from bpmn_adapt.application.service import RuntimeAdaptationApplication
from bpmn_adapt.providers.manager import ProviderManager

def main():
    mgr = ProviderManager()
    openrouter_cfg = mgr.get_provider("openrouter")
    api_key = openrouter_cfg.api_key or os.getenv("OPENROUTER_API_KEY", "")
    mgr.update('openrouter', {
        'api_key': api_key,
        'model': 'nvidia/nemotron-3.5-lightning:free',
        'enabled': True,
        'priority': 1
    })

    client = mgr.build_client('openrouter')
    settings = Settings.load(overrides={'llm_mode': 'live'})
    app = RuntimeAdaptationApplication.from_settings(settings)
    app.llm = client
    app.orchestrator.llm = client
    app.orchestrator.analyst.llm = client
    app.orchestrator.modeler.llm = client
    app.orchestrator.experimenter.llm = client

    t0 = time.monotonic()
    print("Executing live adaptation with OpenRouter (nvidia/nemotron-3.5-lightning:free)...")
    res = app.adapt_folder(
        "E:/Implemention_dataset enriched/Camunda-Dispatch of goods",
        "Remove the task 'Package goods'",
        target="Package goods",
        operation="REMOVE",
        state_id="state_1"
    )
    dur = round(time.monotonic() - t0, 2)
    print(f"COMPLETED successfully in {dur}s!")
    print(f"Status: {res.status}")
    print(f"Decision: {res.decision.status}")
    print(f"Category: {res.decision.rejection_category}")
    print(f"Timing: {res.decision.proposed_timing}")
    print(f"Reason: {res.decision.reason}")
    print(f"Rule IDs: {res.decision.rule_ids}")
    print(f"Resource IDs: {res.decision.resource_ids}")
    print(f"Candidate Generated: {bool(res.candidate)}")
    if res.candidate:
        print(f"Candidate Changes Count: {len(res.candidate.changes)}")
        print(f"Candidate Checksum: {res.candidate.checksum}")
    print(f"Experiment Passed: {res.experiment.passed if res.experiment else None}")

    # Save output for verification
    out_file = Path("artifacts/live_openrouter_test_result.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(res.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved full result artifact to: {out_file}")

if __name__ == "__main__":
    main()
