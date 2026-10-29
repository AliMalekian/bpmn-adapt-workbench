from __future__ import annotations
import unittest

from bpmn_adapt.evaluation.metrics import MetricSuite, Observation, GroundTruth, EvaluationStatus
from tests.unit.test_bpmn_semantics import VALID


class MetricSuiteTests(unittest.TestCase):
    def test_graph_edit_restoration_and_aggregate_token_preservation(self):
        changed = VALID.replace('<userTask id="task" name="Review"/>',
                                '<serviceTask id="task" name="Review"/>')
        observation = Observation("s", "hybrid", "PASS", bpmn_xml=changed,
                                  token_mappings={"task":"task","end":"missing"},
                                  expected_tokens=("task","end"), latency_seconds=.2)
        truth = GroundTruth(expected_decision="PASS", oracle_bpmn_xml=VALID,
                            expected_tokens=("task","end"))
        record = MetricSuite().evaluate(observation, truth)
        self.assertEqual(record.status, EvaluationStatus.EVALUATED)
        self.assertGreater(record.metrics["graph_edit_distance"], 0)
        self.assertEqual(record.metrics["token_preservation"], .5)
        self.assertLess(record.metrics["restoration_similarity"], 1)

    def test_missing_or_contradictory_truth_is_not_evaluable(self):
        suite=MetricSuite(); observation=Observation("s","hybrid","PASS")
        missing=suite.evaluate(observation,GroundTruth())
        contradictory=suite.evaluate(observation,GroundTruth(expected_decision="PASS",
                                                              contradictory=True))
        self.assertEqual(missing.status,EvaluationStatus.NOT_EVALUABLE)
        self.assertEqual(contradictory.status,EvaluationStatus.NOT_EVALUABLE)
        self.assertEqual(missing.denominator,0)


if __name__ == "__main__": unittest.main()
