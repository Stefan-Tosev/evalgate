import tempfile
import unittest
from pathlib import Path

from evalgate.cases import CaseError, discover, load_suite


def write(tmp: str, body: str, name: str = "s.toml") -> Path:
    path = Path(tmp) / name
    path.write_text(body, encoding="utf-8")
    return path


MINIMAL = """
[suite]
name = "s"

[[case]]
id = "a"
prompt = "p"
[[case.assert]]
type = "contains"
value = "x"
"""


class TestLoading(unittest.TestCase):
    def test_minimal_suite(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = load_suite(write(tmp, MINIMAL))
            self.assertEqual(s.name, "s")
            self.assertEqual(s.cases[0].id, "a")
            self.assertEqual(s.model, "claude-opus-5")
            self.assertEqual(s.samples, 3)

    def test_a_case_with_no_assertions_is_rejected(self):
        body = '[suite]\nname="s"\n[[case]]\nid="a"\nprompt="p"\n'
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(CaseError) as ctx:
                load_suite(write(tmp, body))
            self.assertIn("asserts nothing", str(ctx.exception))

    def test_duplicate_ids_are_rejected(self):
        body = MINIMAL + '\n[[case]]\nid = "a"\nprompt = "q"\n[[case.assert]]\ntype = "json_valid"\n'
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(CaseError) as ctx:
                load_suite(write(tmp, body))
            self.assertIn("duplicate", str(ctx.exception))

    def test_missing_prompt_is_rejected(self):
        body = '[suite]\nname="s"\n[[case]]\nid="a"\n[[case.assert]]\ntype="json_valid"\n'
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(CaseError):
                load_suite(write(tmp, body))

    def test_malformed_toml_names_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "[suite\nname=")
            with self.assertRaises(CaseError) as ctx:
                load_suite(path)
            self.assertIn("s.toml", str(ctx.exception))


class TestThresholdResolution(unittest.TestCase):
    def test_case_overrides_suite(self):
        body = """
[suite]
name = "s"
samples = 3
min_pass_rate = 1.0

[[case]]
id = "a"
prompt = "p"
samples = 9
min_pass_rate = 0.5
[[case.assert]]
type = "json_valid"
"""
        with tempfile.TemporaryDirectory() as tmp:
            s = load_suite(write(tmp, body))
            self.assertEqual(s.samples_for(s.cases[0]), 9)
            self.assertEqual(s.threshold_for(s.cases[0]), 0.5)

    def test_suite_defaults_apply_when_case_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = load_suite(write(tmp, MINIMAL))
            self.assertEqual(s.samples_for(s.cases[0]), 3)
            self.assertEqual(s.threshold_for(s.cases[0]), 1.0)


class TestDiscovery(unittest.TestCase):
    def test_directory_loads_every_toml(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, MINIMAL, "one.toml")
            write(tmp, MINIMAL.replace('id = "a"', 'id = "b"'), "two.toml")
            self.assertEqual(len(discover(Path(tmp))), 2)

    def test_empty_directory_is_an_error_not_a_silent_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(CaseError):
                discover(Path(tmp))


class TestShippedSuites(unittest.TestCase):
    def test_the_repo_cases_load(self):
        """The sample suites are part of the contract — a broken one is a bug."""
        root = Path(__file__).resolve().parent.parent / "cases"
        suites = discover(root)
        self.assertTrue(suites)
        for s in suites:
            for c in s.cases:
                self.assertTrue(c.assertions, f"{s.name}/{c.id} has no assertions")


if __name__ == "__main__":
    unittest.main()
