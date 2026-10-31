from pathlib import Path
from bpmn_adapt.config import Settings
from bpmn_adapt.application.service import RuntimeAdaptationApplication

s = Settings.load(overrides={'llm_mode': 'live', 'embedding_provider': 'sentence_transformers'})
app = RuntimeAdaptationApplication.from_settings(s)
folder = Path("E:/Implemention_dataset enriched/Camunda-Dispatch of goods")
bundle = app.ingest(folder)

print("Ingested bundle successfully.")
print("Definition process_id:", bundle.definition.process_id)

for op, text in [("REMOVE", "Remove Package goods task"), ("ADD", "Restore Package goods task")]:
    ev_list = app.rag.retrieve(text, process_id=bundle.definition.process_id, operation=op, source_version_id=None, run_id="test-run")
    print(f"\nOperation {op} retrieved {len(ev_list)} items:")
    for ev in ev_list:
        print(f"  - [{ev.decision}] Score: {ev.final_score:.3f} | ID: {ev.evidence_id}")
        print(f"    Text: {ev.text[:70]}...")

print("\nPipeline verification successful!")
