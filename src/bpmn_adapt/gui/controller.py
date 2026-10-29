"""Headless GUI controller with one-to-one application/CLI parity."""
from __future__ import annotations

import threading


class ThreadLocalGuiController:
    """Build one application object per worker thread.

    SQLite connections are thread-affine by default.  The Tk app submits user
    actions to background worker threads, so the controller used by the GUI must
    not share the application instance that was created on the Tk thread.
    """

    def __init__(self,application_factory):
        self._application_factory=application_factory
        self._local=threading.local()

    def _controller(self):
        controller=getattr(self._local,"controller",None)
        if controller is None:
            controller=GuiController(self._application_factory())
            self._local.controller=controller
        return controller

    def close(self):
        controller=getattr(self._local,"controller",None)
        if controller is not None:
            close=getattr(controller.application,"close",None)
            if callable(close):
                close()
            self._local.controller=None

    def __getattr__(self,name):
        def call(*args,**kwargs):
            controller=self._controller()
            return getattr(controller,name)(*args,**kwargs)
        return call


class GuiController:
    def __init__(self,application): self.application=application
    @classmethod
    def thread_local_factory(cls,application_factory): return ThreadLocalGuiController(application_factory)
    def ingest(self,folder): return self.application.ingest(folder).definition.to_dict()
    def index_rag(self,folder): return self.application.index_rag_folder(folder)
    def revoke_rag(self,evidence_id,reason): return self.application.revoke_rag(evidence_id,reason)
    def analyse(self,folder,request,target="",state_id=None): return self.application.analyse_folder(folder,request,target=target or None,state_id=state_id).to_dict()
    def plan(self,folder,request,target="",state_id=None): return self.application.plan_folder(folder,request,target=target or None,state_id=state_id)
    def adapt(self,folder,request,target="",state_id=None,operation=None,run_id=None): return self.application.adapt_folder(folder,request,target=target or None,state_id=state_id,operation=operation,run_id=run_id).to_dict()
    def validate(self,folder): return self.application.validate_folder(folder)
    def simulate(self,folder): return self.application.simulate_folder(folder)
    def deploy(self,folder,run_id=None,create_instance=False,variables=None): return self.application.deploy_folder(folder,run_id=run_id,create_instance=create_instance,variables=variables)
    def migrate(self,instance,target,mappings,run_id=None): return self.application.migrate_instance(instance,target,mappings,run_id=run_id)
    def approve(self,run_id,reason,actor="user"): return self.application.record_approval(run_id,"APPROVE",reason,actor)
    def reject(self,run_id,reason,actor="user"): return self.application.record_approval(run_id,"REJECT",reason,actor)
    def inspect(self,folder=None,instance_id=None): return self.application.inspect(folder,instance_id)
    def evaluate(self,folder): return self.application.evaluate_folder(folder)
    def baseline(self,folder,variant=None): return self.application.baseline_folder(folder,variant)
    def batch(self,folders,request=None): return self.application.batch_folders(folders,request)
    def report(self,folder): return self.application.report_folder(folder)
    def export(self,run_id,destination): return {"archive":str(self.application.export_run(run_id,destination))}
    def replay(self,run_or_archive): return self.application.replay_run(run_or_archive).to_dict()
