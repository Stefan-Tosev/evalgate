"""The checks a single sample can fail.

Every assertion answers one question: *did this output satisfy the contract?*
An assertion never knows how many times the case was run, and never sees the
other samples — the flake arithmetic belongs to the runner, not here.

`judge` is the exception that proves the rule: it needs to call a model to
reach a verdict, so it takes the provider as a parameter. It is still a pure
pass/fail on one sample.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Check:
    """The outcome of one assertion against one sample."""

    kind: str
    passed: bool
    detail: str = ""


class AssertionError_(ValueError):
    """A malformed assertion — a bug in the case file, not a model failure."""


# --------------------------------------------------------------------------
# a deliberately small JSON Schema subset
# --------------------------------------------------------------------------

_TYPES: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


def validate_schema(value: Any, schema: dict, path: str = "$") -> list[str]:
    """Validate `value` against a subset of JSON Schema.

    Supported: type, required, properties, items, enum. Everything else in a
    schema is ignored rather than rejected — the point is to catch the failures
    a model actually produces (missing field, wrong type, invented enum value),
    not to be a conformant validator. Returns a list of human-readable errors;
    empty means valid.
    """
    errors: list[str] = []

    expected = schema.get("type")
    if expected is not None:
        py = _TYPES.get(expected)
        if py is None:
            raise AssertionError_(f"unknown schema type {expected!r} at {path}")
        # bool is a subclass of int in Python; JSON treats them as distinct
        if expected in ("number", "integer") and isinstance(value, bool):
            errors.append(f"{path}: expected {expected}, got boolean")
            return errors
        if not isinstance(value, py):
            errors.append(f"{path}: expected {expected}, got {type(value).__name__}")
            return errors

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in {schema['enum']!r}")

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required key {key!r}")
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                errors.extend(validate_schema(value[key], sub, f"{path}.{key}"))

    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            errors.extend(validate_schema(item, schema["items"], f"{path}[{i}]"))

    return errors


# --------------------------------------------------------------------------
# the assertions
# --------------------------------------------------------------------------


def _text(spec: dict, key: str) -> str:
    if key not in spec:
        raise AssertionError_(f"assertion {spec.get('type')!r} needs a {key!r} field")
    return str(spec[key])


def check(spec: dict, sample, provider=None) -> Check:
    """Run one assertion against one sample.

    `sample` is a runner.Sample; `provider` is only consulted by `judge`.
    """
    kind = spec.get("type")
    if not kind:
        raise AssertionError_("assertion is missing its 'type'")

    out = sample.text
    ci = bool(spec.get("ignore_case", False))
    hay = out.lower() if ci else out

    if kind == "contains":
        want = _text(spec, "value")
        needle = want.lower() if ci else want
        ok = needle in hay
        return Check(kind, ok, "" if ok else f"missing {want!r}")

    if kind == "not_contains":
        want = _text(spec, "value")
        needle = want.lower() if ci else want
        ok = needle not in hay
        return Check(kind, ok, "" if ok else f"unexpectedly present: {want!r}")

    if kind == "equals":
        want = _text(spec, "value")
        got = out.strip() if spec.get("strip", True) else out
        if ci:
            got, want = got.lower(), want.lower()
        ok = got == want
        return Check(kind, ok, "" if ok else f"got {got[:120]!r}")

    if kind == "regex":
        pattern = _text(spec, "pattern")
        flags = re.IGNORECASE if ci else 0
        ok = re.search(pattern, out, flags) is not None
        return Check(kind, ok, "" if ok else f"no match for /{pattern}/")

    if kind in ("json_valid", "json_schema"):
        raw = _extract_json(out)
        if raw is None:
            return Check(kind, False, "no JSON object or array found in output")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            return Check(kind, False, f"invalid JSON: {exc.msg} at char {exc.pos}")
        if kind == "json_valid":
            return Check(kind, True)
        schema = spec.get("schema")
        if not isinstance(schema, dict):
            raise AssertionError_("json_schema assertion needs a 'schema' table")
        errors = validate_schema(parsed, schema)
        return Check(kind, not errors, "; ".join(errors[:3]))

    if kind == "max_latency_ms":
        limit = float(spec["value"])
        ok = sample.latency_ms <= limit
        return Check(kind, ok, "" if ok else f"{sample.latency_ms:.0f}ms > {limit:.0f}ms")

    if kind == "max_output_tokens":
        limit = int(spec["value"])
        ok = sample.output_tokens <= limit
        return Check(kind, ok, "" if ok else f"{sample.output_tokens} > {limit}")

    if kind == "judge":
        if provider is None:
            raise AssertionError_("judge assertion requires a provider")
        rubric = _text(spec, "rubric")
        verdict = provider.judge(rubric=rubric, output=out, prompt=sample.prompt)
        return Check(kind, verdict.passed, verdict.reason)

    raise AssertionError_(f"unknown assertion type {kind!r}")


def _extract_json(text: str) -> str | None:
    """Pull the first balanced JSON object or array out of a model response.

    Models wrap JSON in prose and fences even when told not to. Extracting is
    the honest thing to do: the test is whether the data is right, and a
    separate assertion can require that nothing surrounds it.
    """
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        depth, in_string, escaped = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    return None
