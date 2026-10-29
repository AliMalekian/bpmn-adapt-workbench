import unittest
from bpmn_adapt.retrieval.metrics import retrieval_metrics


class RetrievalMetricTests(unittest.TestCase):
    def test_standard_metrics(self):
        metrics = retrieval_metrics(["x", "a", "b"], {"a", "b"}, 3)
        self.assertEqual(metrics["recall@3"], 1.0)
        self.assertEqual(metrics["mrr"], 0.5)
        self.assertGreater(metrics["ndcg@3"], 0.6)


if __name__ == "__main__": unittest.main()
