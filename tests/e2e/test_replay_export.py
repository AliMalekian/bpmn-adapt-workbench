from __future__ import annotations
from pathlib import Path
import tempfile
import unittest
import zipfile

from bpmn_adapt.application.service import RuntimeAdaptationApplication
from bpmn_adapt.config import Settings
from tests.test_ingestion_bpmn import IngestionAndBpmnTests


class ReplayExportTests(unittest.TestCase):
    def test_export_checksums_and_replay_reproduce_an_approved_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); folder=IngestionAndBpmnTests().make_folder(root)
            (folder/"Rules.txt").write_text("1. The process must have a start event.\n")
            app=RuntimeAdaptationApplication.from_settings(Settings(
                database_url=f"sqlite:///{root/'db.sqlite'}",output_root=root/"runs"))
            result=app.adapt_folder(folder,"remove Task B",target="Task B")
            archive=app.export_run(result.run_id,root/"export.zip")
            self.assertTrue(zipfile.is_zipfile(archive))
            replay=app.replay_run(archive)
            self.assertEqual(replay.status,"approved")
            self.assertNotEqual(replay.run_id,result.run_id)
            app.close()


if __name__ == "__main__": unittest.main()
