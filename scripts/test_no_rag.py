from pathlib import Path
from bpmn_adapt.config import Settings
from bpmn_adapt.application.service import RuntimeAdaptationApplication
from bpmn_adapt.providers.manager import ProviderManager

def test_no_rag():
    settings = Settings.load(overrides={"llm_mode": "live"})
    app = RuntimeAdaptationApplication.from_settings(settings)
    mgr = ProviderManager()
    client = mgr.build_client("um-llm1-gemma4")
    app.llm = client
    app.orchestrator.llm = client
    app.orchestrator.analyst.llm = client
    app.orchestrator.analyst.enable_rag = False  # NO RAG!
    app.orchestrator.modeler.llm = client
    app.orchestrator.experimenter.llm = client

    folder = Path("E:/Implemention_dataset enriched/Camunda-Dispatch of goods")
    req = "Remove the task 'Package goods'"
    print("Testing with enable_rag = False...")
    res = app.adapt_folder(folder, req, target="Package goods", operation="REMOVE")
    print(f"Decision Status: {res.decision.status.value}")
    print(f"Reason: {res.decision.reason[:80]}...")
    print("Execution completed with ZERO errors!")

if __name__ == "__main__":
    test_no_rag()
