import json
import tempfile
import unittest
from pathlib import Path

from evalgate import baseline
from evalgate.runner import CaseResult, RunResult, Sample, SampleResult


def result_with(rates: dict[str, float], samples: int = 4, threshold: float = 0.0) -> RunResult:
    """Build a RunResult with exact pass rates, without running anything."""
    cases = []
    for case_id, rate in rates.items():
        passes = round(rate * samples)
        results = []
        for i in range(samples):
            s = Sample("p", "t", 1.0, 1, 1)
            r = SampleResult(s)
            if i >= passes:
                r.error = "forced failure"
            results.append(r)
        cases.append(CaseResult(case_id, "suite", threshold, results))
    return RunResult(cases=cases, provider="mock", model="mock-1")


class TestSnapshotRoundTrip(unittest.TestCase):
    def test_write_then_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "baseline.json"
            baseline.write(path, result_with({"a": 1.0, "b": 0.5}))
            loaded = baseline.read(path)
            self.assertEqual(loaded["cases"]["a"]["pass_rate"], 1.0)
            self.assertEqual(loaded["cases"]["b"]["pass_rate"], 0.5)
            self.assertEqual(loaded["format"], baseline.FORMAT_VERSION)

    def test_missing_baseline_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(baseline.read(Path(tmp) / "absent.json"))

    def test_wrong_format_version_is_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.json"
            path.write_text(json.dumps({"format": 99, "cases": {}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                baseline.read(path)


class TestComparison(unittest.TestCase):
    def setUp(self):
        self.previous = baseline.snapshot(result_with({"a": 1.0, "b": 1.0, "gone": 1.0}))

    def test_a_drop_is_a_regression(self):
        cmp = baseline.compare(result_with({"a": 0.5, "b": 1.0}), self.previous)
        self.assertEqual([d.case_id for d in cmp.regressions], ["a"])
        self.assertFalse(cmp.clean)

    def test_tolerance_absorbs_one_sample_of_noise(self):
        run = result_with({"a": 0.75, "b": 1.0})
        strict = baseline.compare(run, self.previous)
        lenient = baseline.compare(run, self.previous, tolerance=0.25)
        self.assertTrue(strict.regressions)
        self.assertFalse(lenient.regressions)

    def test_a_deleted_case_is_not_clean(self):
        cmp = baseline.compare(result_with({"a": 1.0, "b": 1.0}), self.previous)
        self.assertEqual(cmp.removed, ["gone"])
        self.assertFalse(cmp.clean, "a silently deleted case must not pass the gate")

    def test_a_new_case_is_reported_but_does_not_fail_the_gate(self):
        run = result_with({"a": 1.0, "b": 1.0, "gone": 1.0, "fresh": 0.0})
        cmp = baseline.compare(run, self.previous)
        self.assertEqual(cmp.added, ["fresh"])
        self.assertTrue(cmp.clean)

    def test_improvements_are_surfaced(self):
        previous = baseline.snapshot(result_with({"a": 0.5}))
        cmp = baseline.compare(result_with({"a": 1.0}), previous)
        self.assertEqual([d.case_id for d in cmp.improvements], ["a"])
        self.assertTrue(cmp.clean)


if __name__ == "__main__":
    unittest.main()
