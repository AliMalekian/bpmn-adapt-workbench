from __future__ import annotations
import unittest

from bpmn_adapt.evaluation.statistics import StatisticalAnalyzer


class StatisticalTests(unittest.TestCase):
    def test_binary_and_continuous_paired_tests_effects_ci_and_holm(self):
        analyzer=StatisticalAnalyzer(seed=7,bootstrap_samples=300,permutation_samples=500)
        binary=analyzer.compare_binary([1,1,0,1,0,1],[0,1,0,0,1,0])
        self.assertEqual(binary.test,"mcnemar_exact")
        continuous=analyzer.compare_continuous([1,2,3,4,5],[2,3,5,6,8])
        self.assertIn(continuous.test,{"paired_t","wilcoxon","permutation"})
        self.assertIsNotNone(continuous.confidence_interval)
        corrected=analyzer.holm({"a":.01,"b":.04,"c":.2},.05)
        self.assertLessEqual(corrected["a"]["adjusted_p"],corrected["b"]["adjusted_p"])

    def test_statistics_are_deterministic(self):
        values=([1,2,2,4],[2,2,4,8])
        self.assertEqual(StatisticalAnalyzer(seed=2,bootstrap_samples=100).compare_continuous(*values),
                         StatisticalAnalyzer(seed=2,bootstrap_samples=100).compare_continuous(*values))


if __name__ == "__main__": unittest.main()
