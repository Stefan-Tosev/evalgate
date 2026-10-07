import unittest

from evalgate import assertions
from evalgate.runner import Sample


def sample(text: str, latency_ms: float = 10.0, output_tokens: int = 5) -> Sample:
    return Sample("prompt", text, latency_ms, 10, output_tokens)


class TestTextAssertions(unittest.TestCase):
    def test_contains_and_case_folding(self):
        s = sample("The TOTAL is 42")
        self.assertTrue(assertions.check({"type": "contains", "value": "TOTAL"}, s).passed)
        self.assertFalse(assertions.check({"type": "contains", "value": "total"}, s).passed)
        self.assertTrue(
            assertions.check({"type": "contains", "value": "total", "ignore_case": True}, s).passed
        )

    def test_not_contains_reports_the_offending_value(self):
        result = assertions.check({"type": "not_contains", "value": "refund"}, sample("full refund"))
        self.assertFalse(result.passed)
        self.assertIn("refund", result.detail)

    def test_equals_strips_by_default(self):
        s = sample("  yes\n")
        self.assertTrue(assertions.check({"type": "equals", "value": "yes"}, s).passed)
        self.assertFalse(assertions.check({"type": "equals", "value": "yes", "strip": False}, s).passed)

    def test_regex(self):
        s = sample("order #4471 shipped")
        self.assertTrue(assertions.check({"type": "regex", "pattern": r"#\d{4}"}, s).passed)
        self.assertFalse(assertions.check({"type": "regex", "pattern": r"#\d{5}"}, s).passed)

    def test_unknown_type_is_a_suite_defect(self):
        with self.assertRaises(assertions.AssertionError_):
            assertions.check({"type": "vibes"}, sample("x"))

    def test_missing_field_is_a_suite_defect(self):
        with self.assertRaises(assertions.AssertionError_):
            assertions.check({"type": "contains"}, sample("x"))


class TestJSONExtraction(unittest.TestCase):
    def test_finds_json_inside_prose_and_fences(self):
        text = 'Sure! Here is the data:\n```json\n{"total": 42.4}\n```\nLet me know.'
        self.assertTrue(assertions.check({"type": "json_valid"}, sample(text)).passed)

    def test_braces_inside_strings_do_not_end_the_object(self):
        text = '{"note": "a } inside a string", "ok": true}'
        self.assertEqual(assertions._extract_json(text), text)

    def test_escaped_quote_inside_string(self):
        text = r'{"note": "he said \"hi\" }", "ok": true}'
        self.assertEqual(assertions._extract_json(text), text)

    def test_no_json_at_all(self):
        result = assertions.check({"type": "json_valid"}, sample("I cannot help with that."))
        self.assertFalse(result.passed)
        self.assertIn("no JSON", result.detail)

    def test_malformed_json_reports_position(self):
        result = assertions.check({"type": "json_valid"}, sample('{"total": }'))
        self.assertFalse(result.passed)
        self.assertIn("invalid JSON", result.detail)


class TestSchema(unittest.TestCase):
    schema = {
        "type": "object",
        "required": ["vendor", "total"],
        "properties": {"vendor": {"type": "string"}, "total": {"type": "number"}},
    }

    def test_valid(self):
        s = sample('{"vendor": "Acme", "total": 42.4}')
        self.assertTrue(assertions.check({"type": "json_schema", "schema": self.schema}, s).passed)

    def test_missing_required_key(self):
        s = sample('{"vendor": "Acme"}')
        result = assertions.check({"type": "json_schema", "schema": self.schema}, s)
        self.assertFalse(result.passed)
        self.assertIn("missing required key 'total'", result.detail)

    def test_wrong_type(self):
        s = sample('{"vendor": "Acme", "total": "42.40"}')
        result = assertions.check({"type": "json_schema", "schema": self.schema}, s)
        self.assertFalse(result.passed)
        self.assertIn("expected number", result.detail)

    def test_booleans_are_not_numbers(self):
        errors = assertions.validate_schema(True, {"type": "number"})
        self.assertTrue(errors)

    def test_enum_and_nested_items(self):
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "object", "properties": {"kind": {"enum": ["a", "b"]}}},
                }
            },
        }
        ok = assertions.validate_schema({"items": [{"kind": "a"}]}, schema)
        bad = assertions.validate_schema({"items": [{"kind": "z"}]}, schema)
        self.assertEqual(ok, [])
        self.assertIn("not in", bad[0])


class TestBudgetAssertions(unittest.TestCase):
    def test_latency(self):
        s = sample("x", latency_ms=900)
        self.assertTrue(assertions.check({"type": "max_latency_ms", "value": 1000}, s).passed)
        self.assertFalse(assertions.check({"type": "max_latency_ms", "value": 500}, s).passed)

    def test_output_tokens(self):
        s = sample("x", output_tokens=130)
        self.assertFalse(assertions.check({"type": "max_output_tokens", "value": 120}, s).passed)


if __name__ == "__main__":
    unittest.main()
