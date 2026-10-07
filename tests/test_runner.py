"""The tests that matter most: does the flake arithmetic actually work?

A harness that reports a flaky case as a pass — or as a failure — depending on
which sample happened to run last is worse than no harness, because it teaches
people to distrust the number.
"""

import unittest

from evalgate.cases import Case, Suite
from evalgate.providers.mock import MockProvider
from evalgate.runner import ERROR, FAILED, FLAKY, STABLE, run_case, run_suites


def suite(**kwargs) -> Suite:
    from pathlib import Path

    defaults = dict(name="t", path=Path("t.toml"), cases=(), samples=4, min_pass_rate=1.0)
    defaults.update(kwargs)
    return Suite(**defaults)


def case(**kwargs) -> Case:
    defaults = dict(
        id="c",
        prompt="p",
        assertions=({"type": "contains", "value": "good"},),
        mock={"response": "good"},
    )
    defaults.update(kwargs)
    return Case(**defaults)


class TestVerdicts(unittest.TestCase):
    def test_all_samples_pass_is_stable(self):
        result = run_case(suite(), case(), MockProvider(seed=1))
        self.assertEqual(result.status, STABLE)
        self.assertEqual(result.pass_rate, 1.0)
        self.assertEqual(result.samples, 4)

    def test_all_samples_fail(self):
        c = case(mock={"response": "bad"})
        result = run_case(suite(), c, MockProvider(seed=1))
        self.assertEqual(result.status, FAILED)
        self.assertEqual(result.pass_rate, 0.0)

    def test_partial_pass_below_threshold_is_a_failure(self):
        # flake_rate 1.0 with a passing "response" means every sample flakes.
        c = case(mock={"response": "good", "flake": "bad", "flake_rate": 1.0})
        result = run_case(suite(min_pass_rate=1.0), c, MockProvider(seed=7))
        self.assertEqual(result.status, FAILED)

    def test_partial_pass_above_threshold_is_flaky_not_stable(self):
        c = case(
            samples=20,
            min_pass_rate=0.5,
            mock={"response": "good", "flake": "bad", "flake_rate": 0.25},
        )
        result = run_case(suite(samples=20, min_pass_rate=0.5), c, MockProvider(seed=11))
        self.assertEqual(result.status, FLAKY)
        self.assertTrue(result.gated_pass, "a flaky case above threshold still passes the gate")
        self.assertLess(result.pass_rate, 1.0)
        self.assertGreater(result.pass_rate, 0.5)

    def test_case_level_threshold_overrides_the_suite(self):
        c = case(min_pass_rate=0.0, mock={"response": "bad"})
        result = run_case(suite(min_pass_rate=1.0), c, MockProvider(seed=1))
        self.assertEqual(result.threshold, 0.0)
        self.assertTrue(result.gated_pass)

    def test_case_level_sample_count_overrides_the_suite(self):
        result = run_case(suite(samples=4), case(samples=9), MockProvider(seed=1))
        self.assertEqual(result.samples, 9)


class TestErrorHandling(unittest.TestCase):
    def test_a_broken_assertion_is_an_error_not_a_model_failure(self):
        c = case(assertions=({"type": "no_such_assertion"},))
        result = run_case(suite(), c, MockProvider(seed=1))
        self.assertEqual(result.status, ERROR)
        self.assertIn("bad assertion", result.first_failure())

    def test_a_provider_exception_becomes_a_result(self):
        class Exploding(MockProvider):
            def complete(self, **kwargs):
                raise RuntimeError("connection reset")

        result = run_case(suite(), case(), Exploding(seed=1))
        self.assertEqual(result.status, ERROR)
        self.assertIn("connection reset", result.first_failure())


class TestRunAggregate(unittest.TestCase):
    def test_a_single_failure_fails_the_run(self):
        good = case(id="good")
        bad = case(id="bad", mock={"response": "nope"})
        s = suite(cases=(good, bad))
        result = run_suites([s], MockProvider(seed=1))
        self.assertFalse(result.passed)
        self.assertEqual(len(result.cases), 2)

    def test_token_accounting_is_summed_across_samples(self):
        result = run_suites([suite(cases=(case(),))], MockProvider(seed=1))
        self.assertGreater(result.total_tokens, 0)


class TestJudgePlumbing(unittest.TestCase):
    def test_judge_verdict_reaches_the_check(self):
        c = case(
            assertions=({"type": "judge", "rubric": "credit|30"},),
            mock={"response": "store credit, and the 30 day window has passed"},
        )
        self.assertEqual(run_case(suite(), c, MockProvider(seed=1)).status, STABLE)

    def test_judge_failure_is_reported_with_its_reason(self):
        c = case(
            assertions=({"type": "judge", "rubric": "credit|30"},),
            mock={"response": "here is a full refund"},
        )
        result = run_case(suite(), c, MockProvider(seed=1))
        self.assertEqual(result.status, FAILED)
        self.assertIn("rubric not satisfied", result.first_failure())


if __name__ == "__main__":
    unittest.main()
