from __future__ import annotations
import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path("src").resolve()))

from bpmn_adapt.config import Settings
from bpmn_adapt.application.service import RuntimeAdaptationApplication
from bpmn_adapt.evaluation.runner import EvaluationRunner

def main():
    import dataclasses
    settings = dataclasses.replace(Settings.load(), llm_mode="mock")
    app = RuntimeAdaptationApplication.from_settings(settings)
    runner = EvaluationRunner(app)
    
    test_folders = [
        "Pmo-3D printer",
        "Pmo-Bottling Machine",
        "Pmo-Burger Seller",
        "Mangler-Car Service",
        "Mangler-Chainsaw",
        "Camunda-Credit-scoring",
        "Camunda-Dispatch of goods"
    ]
    
    print("=" * 60)
    print("RUNNING OFFICIAL GROUND TRUTH BENCHMARKS ACROSS DATASETS")
    print("=" * 60)
    
    all_results = {}
    for f in test_folders:
        try:
            res = runner.evaluate(f)
            all_results[f] = res
            layers = res.get("ground_truth_layers", {})
            abl = res.get("ablations", {})
            print(f"\n[DATASET] {f}:")
            print(f"  Cases: {len(res.get('cases', []))}")
            print(f"  Decision Accuracy (Hybrid): {layers.get('request_decision', {}).get('accuracy')}")
            print(f"  Constraint Accuracy (Hybrid): {layers.get('constraint_reasoning', {}).get('accuracy')}")
            print("  Ablation Decision Accuracies:")
            for mode, data in abl.items():
                print(f"    - {mode:20s}: Dec Acc = {data.get('decision_accuracy')}, Const Acc = {data.get('constraint_reasoning_accuracy')}, Cov = {data.get('retrieval_coverage')}")
        except Exception as e:
            print(f"Error evaluating {f}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
