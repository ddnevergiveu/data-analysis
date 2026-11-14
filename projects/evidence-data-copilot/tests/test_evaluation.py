"""A real engine/planner regression suite, without mocked analysis answers."""

import json
import unittest
from unittest.mock import patch

from evidence_copilot.evaluation import evaluate


class EvaluationTests(unittest.TestCase):
    def test_hand_calculated_execution_planning_and_refusal(self):
        report = evaluate()
        self.assertEqual(report["total"], 19)
        self.assertEqual(report["failed"], 0, json.dumps(report, ensure_ascii=False, indent=2))
        self.assertEqual(report["passed"], 19)
        self.assertTrue(report["all_passed"])
        categories = {name: sum(case["category"] == name for case in report["cases"])
                      for name in ("query_execution", "rule_planning", "query_rejection")}
        self.assertEqual(categories, {"query_execution": 6, "rule_planning": 6, "query_rejection": 7})
        self.assertIn("not measured", report["scope"]["llm_accuracy"])
        # The CLI can write this artifact with strict JSON, without NaN fallback.
        json.dumps(report, allow_nan=False)

    def test_wrong_answers_cannot_pass(self):
        # Deliberately corrupt the system under test, never the independent oracle.
        with patch("evidence_copilot.engine.QueryEngine.query", return_value={"rows": [[999]], "truncated": False}):
            report = evaluate()
        self.assertEqual(report["passed"], 0)
        self.assertEqual(report["failed"], 19)
        self.assertFalse(report["all_passed"])


if __name__ == "__main__":
    unittest.main()
