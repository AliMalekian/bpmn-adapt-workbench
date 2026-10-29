import unittest
from pathlib import Path
from tests.test_ingestion_bpmn import BPMN


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        from bpmn_adapt.config import Settings
        from bpmn_adapt.llm.embedding import HashEmbeddingClient
        from bpmn_adapt.llm.mock import MockLLMClient
        from bpmn_adapt.persistence.sqlite import SQLiteDatabase
        from bpmn_adapt.retrieval.service import HybridRAGService
        from bpmn_adapt.agents.orchestrator import OrchestratorAgent
        self.db=SQLiteDatabase(":memory:"); self.db.initialize()
        self.db.upsert_process("p1","folder","Demo","Story",BPMN,[],[("RES1","Workers","2")],[("S1","Task B",'{"tokens":["b"]}')])
        self.llm=MockLLMClient(); self.settings=Settings()
        self.rag=HybridRAGService(self.db,HashEmbeddingClient())
        self.agent=OrchestratorAgent(self.db,self.rag,self.llm,self.settings)

    def tearDown(self): self.db.close()

    def request(self,target="Task B"):
        from bpmn_adapt.domain.models import AdaptationRequest,OperationType
        return AdaptationRequest("req-orch","p1",Path("folder"),OperationType.REMOVE,f"remove {target}",target,"p1-source")

    def test_success_runs_all_agents_approves_and_indexes_case(self):
        result=self.agent.run(self.request(),active_tokens={"b"})
        self.assertEqual("approved",result.status)
        self.assertTrue(result.experiment.passed)
        self.assertEqual("approved",self.db.get_run(result.run_id)["status"])
        self.assertEqual(result.candidate.checksum,self.db.get_version(result.candidate.candidate_id)["checksum"])
        self.assertEqual(1,len(self.db.list_rag_cases("p1",active_only=True)))
        event_types=[e["event_type"] for e in result.provenance.events]
        self.assertEqual(["orchestrator_started","analyst_completed","modeler_completed","experimenter_completed","final_approval"],event_types)

    def test_rejected_decision_does_not_index_case(self):
        self.db.execute("INSERT INTO rules(process_id,rule_id,text) VALUES(?,?,?)",("p1","R9","Task B must remain")); self.db.connection.commit()
        result=self.agent.run(self.request(),active_tokens={"b"})
        self.assertEqual("rejected",result.status)
        self.assertEqual([],self.db.list_rag_cases("p1",active_only=True))

    def test_unknown_target_fails_with_provenance_not_uncaught_exception(self):
        result=self.agent.run(self.request(target="Nonexistent activity"),active_tokens=set())
        self.assertEqual("failed",result.status)
        self.assertIsNone(result.candidate)
        self.assertEqual("modeler_error",result.provenance.events[-1]["event_type"])
        self.assertEqual([],self.db.list_rag_cases("p1",active_only=True))

    def test_experiment_failure_is_passed_to_modeler_on_retry(self):
        calls=[]
        original=self.agent.modeler.model
        def recording_model(*args,**kwargs):
            calls.append(kwargs.get("feedback")); return original(*args,**kwargs)
        self.agent.modeler.model=recording_model
        class FailingExperimenter:
            def __init__(self): self.n=0
            def experiment(inner,candidate,*args,**kwargs):
                from bpmn_adapt.domain.models import ExperimentReport
                inner.n+=1
                return ExperimentReport(f"r{inner.n}",candidate.candidate_id,inner.n>1,(),(() if inner.n>1 else ({"type":"deadlock"},)))
        self.agent.experimenter=FailingExperimenter()
        result=self.agent.run(self.request(),active_tokens={"b"})
        self.assertEqual("approved",result.status)
        self.assertIsNone(calls[0])
        self.assertEqual(({"type":"deadlock"},),calls[1])


if __name__ == "__main__": unittest.main()
