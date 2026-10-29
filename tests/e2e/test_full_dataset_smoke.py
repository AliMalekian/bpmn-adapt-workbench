from __future__ import annotations
from pathlib import Path
import tempfile
import unittest

from bpmn_adapt.evaluation.datasets import discover_dataset
from bpmn_adapt.evaluation.manifest import ExperimentManifest
from bpmn_adapt.evaluation.datasets import DatasetExecutor
from bpmn_adapt.config import Settings
from tests.test_ingestion_bpmn import IngestionAndBpmnTests


class FullDatasetSmokeTests(unittest.TestCase):
    def test_resumable_isolated_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); folder=IngestionAndBpmnTests().make_folder(root)
            discovery=discover_dataset(root)
            output=root/"evidence"; manifest=ExperimentManifest(output/"manifest.jsonl")
            settings=Settings(output_root=output/"runs",database_url=f"sqlite:///{output/'base.db'}")
            executor=DatasetExecutor(settings,manifest,output,max_workers=2)
            first=executor.run(discovery.valid,("hybrid",),scenario_kinds=("inspect",))
            second=executor.run(discovery.valid,("hybrid",),scenario_kinds=("inspect",))
            self.assertEqual(first["completed"],1); self.assertEqual(second["skipped"],1)
            self.assertTrue((output/"folders"/discovery.valid[0].folder_id).is_dir())


if __name__ == "__main__": unittest.main()
