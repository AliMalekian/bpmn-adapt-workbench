import unittest
from pathlib import Path

from tests.test_ingestion_bpmn import BPMN


class AgentTests(unittest.TestCase):
    def setUp(self):
        from bpmn_adapt.llm.embedding import HashEmbeddingClient
        from bpmn_adapt.llm.mock import MockLLMClient
        from bpmn_adapt.persistence.sqlite import SQLiteDatabase
        from bpmn_adapt.retrieval.service import HybridRAGService
        self.db=SQLiteDatabase(":memory:"); self.db.initialize()
        self.db.upsert_process("p1", "folder", "Demo", "Story", BPMN, [("R1", "Task A must precede Task B")], [("RES1", "Workers", "2")], [("S1", "Task A", '{"tokens":["a"]}')])
        self.db.create_run("seed", "p1", "fp", "approved")
        self.db.add_rag_case("ev1", "seed", "p1", "p1-source", "REMOVE", "remove Task A", "ACCEPT", "{}")
        self.llm=MockLLMClient()
        self.rag=HybridRAGService(self.db, HashEmbeddingClient())

    def tearDown(self): self.db.close()

    def request(self, target="Task A"):
        from bpmn_adapt.domain.models import AdaptationRequest, OperationType
        return AdaptationRequest("req1", "p1", Path("folder"), OperationType.REMOVE, f"remove {target}", target, "p1-source")

    def test_analyst_db_rule_overrides_accepting_rag_evidence(self):
        from bpmn_adapt.agents.analyst import AnalystAgent
        from bpmn_adapt.domain.models import DecisionStatus
        decision=AnalystAgent(self.db,self.rag,self.llm).analyse(self.request(), run_id="seed")
        self.assertEqual(DecisionStatus.REJECT, decision.status)
        self.assertEqual(("R1",), decision.rule_ids)
        self.assertEqual(("ev1",), decision.evidence_ids)

    def test_modeler_requires_approved_decision_and_builds_migration(self):
        from bpmn_adapt.agents.modeler import ModelerAgent, ModelerAuthorizationError
        from bpmn_adapt.domain.models import DecisionStatus, FeasibilityDecision
        rejected=FeasibilityDecision("d1",DecisionStatus.REJECT,"no",self.request())
        modeler=ModelerAgent(self.llm)
        with self.assertRaises(ModelerAuthorizationError): modeler.model(rejected,BPMN,{"a"})
        approved=FeasibilityDecision("d2",DecisionStatus.APPROVE,"ok",self.request(target="Task B"))
        candidate=modeler.model(approved,BPMN,{"b"})
        self.assertEqual({"b":"end"},candidate.migration.mappings)

    def test_modeler_resolves_natural_language_target_to_real_bpmn_element(self):
        from bpmn_adapt.agents.modeler import ModelerAgent
        from bpmn_adapt.domain.models import DecisionStatus, FeasibilityDecision
        approved=FeasibilityDecision("d3",DecisionStatus.APPROVE,"ok",self.request(target="please remove the Task B activity"))
        candidate=ModelerAgent(self.llm).model(approved,BPMN,{"b"})
        self.assertEqual("b",candidate.changes[0].target_id)

    def test_experimenter_validates_trace_and_token_mapping(self):
        from bpmn_adapt.agents.experimenter import ExperimenterAgent
        from bpmn_adapt.agents.modeler import ModelerAgent
        from bpmn_adapt.domain.models import DecisionStatus, FeasibilityDecision
        approved=FeasibilityDecision("d2",DecisionStatus.APPROVE,"ok",self.request(target="Task B"))
        candidate=ModelerAgent(self.llm).model(approved,BPMN,{"b"})
        report=ExperimenterAgent(self.llm).experiment(candidate)
        self.assertTrue(report.passed, report.failures)
        self.assertTrue(any(trace[-1] == "end" for trace in report.traces))

    def test_simulator_bounds_branching_cycles(self):
        from bpmn_adapt.simulation.engine import simulate
        xml='''<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"><process id="p">
        <startEvent id="s"/><exclusiveGateway id="g"/><task id="a"/><task id="b"/><endEvent id="e"/>
        <sequenceFlow id="f1" sourceRef="s" targetRef="g"/><sequenceFlow id="f2" sourceRef="g" targetRef="a"/>
        <sequenceFlow id="f3" sourceRef="g" targetRef="b"/><sequenceFlow id="f4" sourceRef="a" targetRef="g"/>
        <sequenceFlow id="f5" sourceRef="b" targetRef="e"/></process></definitions>'''
        traces,failures=simulate(xml,max_steps=100,max_states=20)
        self.assertTrue(any(t[-1]=="e" for t in traces))
        self.assertLessEqual(len(traces)+len(failures),20)

    def test_parallel_gateway_waits_for_all_branches(self):
        from bpmn_adapt.simulation.engine import simulate
        xml='''<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"><process id="p">
        <startEvent id="s"/><parallelGateway id="split"/><task id="a"/><task id="b"/><parallelGateway id="join"/><endEvent id="e"/>
        <sequenceFlow id="f1" sourceRef="s" targetRef="split"/><sequenceFlow id="f2" sourceRef="split" targetRef="a"/>
        <sequenceFlow id="f3" sourceRef="split" targetRef="b"/><sequenceFlow id="f4" sourceRef="a" targetRef="join"/>
        <sequenceFlow id="f5" sourceRef="b" targetRef="join"/><sequenceFlow id="f6" sourceRef="join" targetRef="e"/></process></definitions>'''
        traces,failures=simulate(xml)
        self.assertEqual((),failures)
        self.assertTrue(any("a" in trace and "b" in trace and trace[-1]=="e" for trace in traces))


if __name__ == "__main__": unittest.main()
