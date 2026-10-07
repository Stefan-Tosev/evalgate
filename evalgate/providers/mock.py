"""A scripted provider, so the harness itself is testable.

The hardest thing about testing an eval harness is that its input is
non-deterministic by nature. This provider makes non-determinism *scripted*:
a case declares what the model returns and how often it misbehaves, so the
flake arithmetic, the thresholds, and the baseline gate can all be exercised
in CI with no API key and no spend.

    [case.mock]
    response   = "the good answer"
    flake_rate = 0.4                # 40% of samples return the bad answer
    flake      = "the bad answer"
    latency_ms = 120

A case with no [case.mock] table echoes a deterministic digest of its prompt,
which is enough to exercise the plumbing but not the assertions.
"""

from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass


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


class MockProvider:
    name = "mock"

    def __init__(self, model: str = "mock-1", effort: str = "medium", seed: int | None = None):
        self.model = model
        self.effort = effort
        self._rng = random.Random(seed if seed is not None else 0xE7A1)

    def complete(self, *, prompt: str, system: str | None = None, mock: dict | None = None) -> Completion:
        mock = mock or {}
        started = time.perf_counter()

        good = mock.get("response")
        if good is None:
            digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
            good = f"mock:{digest}"

        flake_rate = float(mock.get("flake_rate", 0.0))
        if flake_rate and self._rng.random() < flake_rate:
            text = str(mock.get("flake", ""))
        else:
            text = str(good)

        # A scripted delay, so max_latency_ms assertions are exercisable.
        simulated = float(mock.get("latency_ms", 0.0))
        real = (time.perf_counter() - started) * 1000.0
        return Completion(
            text=text,
            latency_ms=simulated if simulated else real,
            input_tokens=_tokens(prompt) + _tokens(system or ""),
            output_tokens=_tokens(text),
        )

    def judge(self, *, rubric: str, output: str, prompt: str) -> Verdict:
        """A judge with no model behind it: substring containment.

        Deliberately crude. Its job is to prove the judge *plumbing* works —
        that a rubric reaches the judge and a verdict comes back — not to
        stand in for real judgement.
        """
        ok = all(token.lower() in output.lower() for token in rubric.split("|"))
        return Verdict(ok, "mock judge: substring rubric" if ok else "mock judge: rubric not satisfied")


def _tokens(text: str) -> int:
    """A rough token count. Never used for billing — only for assertions."""
    return max(1, len(text) // 4) if text else 0
