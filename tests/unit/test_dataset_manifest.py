from __future__ import annotations
from pathlib import Path
import tempfile
import unittest

from bpmn_adapt.evaluation.datasets import discover_dataset
from bpmn_adapt.evaluation.manifest import ExperimentManifest
from tests.test_ingestion_bpmn import IngestionAndBpmnTests


class DatasetManifestTests(unittest.TestCase):
    def test_discovery_identity_scenarios_invalid_and_duplicate_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); first=IngestionAndBpmnTests().make_folder(root)
            second_root=root/"nested"; second_root.mkdir(); second=IngestionAndBpmnTests().make_folder(second_root)
            invalid=root/"Broken"; invalid.mkdir()
            discovery=discover_dataset(root,recursive=True)
            self.assertEqual(len(discovery.valid),2); self.assertEqual(len(discovery.invalid),1)
            self.assertNotEqual(discovery.valid[0].folder_id,discovery.valid[1].folder_id)
            self.assertTrue(all(item.scenarios for item in discovery.valid))

    def test_resume_and_checksum_drift_are_append_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"manifest.jsonl"; manifest=ExperimentManifest(path)
            manifest.append_result("folder","checksum-1","scenario","hybrid","PASS",{"x":1})
            self.assertTrue(manifest.completed("folder","checksum-1","scenario","hybrid"))
            self.assertFalse(manifest.completed("folder","checksum-2","scenario","hybrid"))
            manifest.append_result("folder","checksum-2","scenario","hybrid","PASS",{"x":2})
            self.assertEqual(len(path.read_text().splitlines()),2)

    def test_resume_key_includes_configuration_and_runner_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest=ExperimentManifest(Path(tmp)/"manifest.jsonl")
            manifest.append_result("folder","checksum","scenario","hybrid","PASS",{},
                                   experiment_fingerprint="config-a",runner_version="v2")
            self.assertTrue(manifest.completed("folder","checksum","scenario","hybrid",
                                               experiment_fingerprint="config-a",runner_version="v2"))
            self.assertFalse(manifest.completed("folder","checksum","scenario","hybrid",
                                                experiment_fingerprint="config-b",runner_version="v2"))
            self.assertFalse(manifest.completed("folder","checksum","scenario","hybrid",
                                                experiment_fingerprint="config-a",runner_version="v3"))


if __name__ == "__main__": unittest.main()
