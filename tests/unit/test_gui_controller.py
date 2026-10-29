from __future__ import annotations
from pathlib import Path
import tempfile
import time
import unittest

from bpmn_adapt.application.service import RuntimeAdaptationApplication
from bpmn_adapt.config import Settings
from bpmn_adapt.gui.controller import GuiController
from bpmn_adapt.gui.workers import TaskWorker


class Application:
    def __getattr__(self,name):
        def call(*args,**kwargs): return {"method":name,"args":args,"kwargs":kwargs}
        return call


class GuiControllerTests(unittest.TestCase):
    def test_controller_exposes_every_cli_use_case_without_direct_db_access(self):
        controller=GuiController(Application())
        names={"ingest","index_rag","revoke_rag","analyse","plan","adapt","validate",
               "simulate","deploy","migrate","approve","reject","inspect","evaluate",
               "baseline","batch","report","export","replay"}
        self.assertTrue(all(callable(getattr(controller,name)) for name in names))
        self.assertFalse(hasattr(controller,"database"))

    def test_worker_reports_completion_error_and_cancellation_via_queue(self):
        worker=TaskWorker(max_workers=1)
        done=worker.submit(lambda: 42)
        failed=worker.submit(lambda: (_ for _ in ()).throw(ValueError("bad")))
        cancelled=worker.submit(lambda cancel_event: cancel_event.wait(1) or "late")
        worker.cancel(cancelled)
        deadline=time.time()+2; events=[]
        while time.time()<deadline and len({event.task_id for event in events if event.kind in {"completed","error","cancelled"}})<3:
            events.extend(worker.poll()); time.sleep(.01)
        kinds={event.task_id:event.kind for event in events if event.kind in {"completed","error","cancelled"}}
        self.assertEqual(kinds[done],"completed"); self.assertEqual(kinds[failed],"error")
        self.assertEqual(kinds[cancelled],"cancelled"); worker.shutdown()

    def test_worker_controller_calls_do_not_reuse_sqlite_connection_across_threads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            settings=Settings(database_url=f"sqlite:///{root/'gui.db'}",output_root=root/"runs")
            worker=TaskWorker(max_workers=1)
            controller=None
            try:
                controller=GuiController.thread_local_factory(lambda: RuntimeAdaptationApplication.from_settings(settings))
                task_id=worker.submit(lambda: controller.inspect("Pmo-3D printer"))
                deadline=time.time()+5; terminal=None
                while time.time()<deadline and terminal is None:
                    for event in worker.poll():
                        if event.task_id==task_id and event.kind in {"completed","error","cancelled"}:
                            terminal=event
                    time.sleep(.01)
                self.assertIsNotNone(terminal)
                self.assertEqual(terminal.kind,"completed",terminal.payload)
                self.assertIn("process",terminal.payload)
            finally:
                worker.shutdown()
                if controller is not None:
                    controller.close()


if __name__ == "__main__": unittest.main()
