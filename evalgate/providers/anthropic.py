"""The Anthropic provider.

The `anthropic` SDK is imported lazily so the core harness — loading cases,
running the mock provider, computing flake rates, gating on the baseline —
keeps working with nothing installed. You only need the dependency at the
moment you actually call a model.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

DEFAULT_MODEL = "claude-opus-5"
JUDGE_MODEL = "claude-opus-5"

# Non-streaming requests risk an SDK HTTP timeout above roughly this ceiling.
MAX_TOKENS = 16_000


@dataclass(frozen=True)
class Verdict:
    passed: bool
    reason: str


@dataclass(frozen=True)
class Completion:
    text: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    stop_reason: str = "end_turn"


class ProviderError(RuntimeError):
    pass


_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "passed": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["passed", "reason"],
    "additionalProperties": False,
}

_JUDGE_SYSTEM = (
    "You grade one model output against one rubric. You are not being asked to "
    "improve the output, only to judge it. Apply the rubric literally: if it does "
    "not require something, its absence is not a failure. Give the reason in one "
    "sentence, citing the specific part of the output that decided it."
)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str = DEFAULT_MODEL, effort: str = "medium", judge_model: str = JUDGE_MODEL):
        try:
            import anthropic  # noqa: PLC0415 — deliberately lazy
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise ProviderError(
                "the anthropic provider needs the SDK: pip install anthropic"
            ) from exc

        if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
            # A profile from `ant auth login` also works, so this is a hint and
            # not a hard failure — the SDK resolves credentials on its own.
            pass

        self._client = anthropic.Anthropic()
        self.model = model
        self.effort = effort
        self.judge_model = judge_model

    def complete(self, *, prompt: str, system: str | None = None, mock: dict | None = None) -> Completion:
        started = time.perf_counter()
        kwargs: dict = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": self.effort},
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        response = self._client.messages.create(**kwargs)
        latency_ms = (time.perf_counter() - started) * 1000.0

        # A refusal is a successful HTTP 200 with an empty or partial content
        # array. Indexing content[0] here would crash the run on exactly the
        # inputs an eval suite most wants to measure.
        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None) if response.stop_details else None
            return Completion(
                text="",
                latency_ms=latency_ms,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                stop_reason=f"refusal:{category}",
            )

        text = "".join(block.text for block in response.content if block.type == "text")
        return Completion(
            text=text,
            latency_ms=latency_ms,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason or "end_turn",
        )

    def judge(self, *, rubric: str, output: str, prompt: str) -> Verdict:
        content = (
            f"<rubric>\n{rubric}\n</rubric>\n\n"
            f"<original_request>\n{prompt}\n</original_request>\n\n"
            f"<output_to_grade>\n{output}\n</output_to_grade>"
        )
        response = self._client.messages.create(
            model=self.judge_model,
            max_tokens=2_000,
            system=_JUDGE_SYSTEM,
            thinking={"type": "adaptive"},
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": _JUDGE_SCHEMA},
            },
            messages=[{"role": "user", "content": content}],
        )

        if response.stop_reason == "refusal":
            return Verdict(False, "judge refused to grade this output")

        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return Verdict(False, f"judge returned unparseable output: {text[:120]!r}")
        return Verdict(bool(parsed.get("passed")), str(parsed.get("reason", "")))
