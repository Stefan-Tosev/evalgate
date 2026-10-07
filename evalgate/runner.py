"""Running a suite, and turning N noisy samples into one verdict.

This is the part that makes the harness a *test* harness rather than a demo.
A single sample tells you almost nothing about a non-deterministic system: the
same prompt can pass four times and fail the fifth, and a suite that runs each
case once will report that as a pass or a failure depending on the weather.

So every case runs N times and the result is a pass *rate*, compared against a
declared threshold. A case that passes 5/5 is stable. A case that passes 3/5 is
flaky, which is a distinct state from failing — it is reported as such rather
than being rounded to whichever verdict the last sample happened to give.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from statistics import mean

from . import assertions
from .cases import Case, Suite

STABLE = "stable"
FLAKY = "flaky"
FAILED = "failed"
ERROR = "error"


@dataclass(frozen=True)
class Sample:
    prompt: str
    text: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    stop_reason: str = "end_turn"


@dataclass
class SampleResult:
    sample: Sample
    checks: list[assertions.Check] = field(default_factory=list)
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.error is None and all(c.passed for c in self.checks)

    def failures(self) -> list[assertions.Check]:
        return [c for c in self.checks if not c.passed]


@dataclass
class CaseResult:
    case_id: str
    suite: str
    threshold: float
    results: list[SampleResult]

    @property
    def samples(self) -> int:
        return len(self.results)

    @property
    def passes(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def pass_rate(self) -> float:
        return self.passes / self.samples if self.samples else 0.0

    @property
    def status(self) -> str:
        if any(r.error for r in self.results):
            return ERROR
        if self.pass_rate < self.threshold:
            return FAILED
        return STABLE if self.pass_rate == 1.0 else FLAKY

    @property
    def gated_pass(self) -> bool:
        """Whether this case clears its own threshold, ignoring flakiness."""
        return self.status in (STABLE, FLAKY)

    @property
    def mean_latency_ms(self) -> float:
        return mean(r.sample.latency_ms for r in self.results) if self.results else 0.0

    @property
    def total_tokens(self) -> int:
        return sum(r.sample.input_tokens + r.sample.output_tokens for r in self.results)

    def first_failure(self) -> str:
        for r in self.results:
            if r.error:
                return r.error
            for c in r.failures():
                return f"{c.kind}: {c.detail}" if c.detail else c.kind
        return ""


@dataclass
class RunResult:
    cases: list[CaseResult]
    provider: str
    model: str

    @property
    def passed(self) -> bool:
        return all(c.gated_pass for c in self.cases)

    def by_id(self) -> dict[str, CaseResult]:
        return {c.case_id: c for c in self.cases}

    @property
    def total_tokens(self) -> int:
        return sum(c.total_tokens for c in self.cases)


def run_case(suite: Suite, case: Case, provider, concurrency: int = 4) -> CaseResult:
    n = suite.samples_for(case)

    def one(_: int) -> SampleResult:
        try:
            completion = provider.complete(
                prompt=case.prompt, system=case.system, mock=case.mock
            )
        except Exception as exc:  # noqa: BLE001 — a provider failure is a result, not a crash
            empty = Sample(case.prompt, "", 0.0, 0, 0, "error")
            return SampleResult(empty, [], error=f"{type(exc).__name__}: {exc}")

        sample = Sample(
            prompt=case.prompt,
            text=completion.text,
            latency_ms=completion.latency_ms,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            stop_reason=getattr(completion, "stop_reason", "end_turn"),
        )
        result = SampleResult(sample)
        for spec in case.assertions:
            try:
                result.checks.append(assertions.check(spec, sample, provider))
            except assertions.AssertionError_ as exc:
                # A malformed assertion is a defect in the suite. Surface it as
                # an error rather than a model failure — otherwise a typo in a
                # case file looks like a regression in the model.
                result.error = f"bad assertion: {exc}"
                break
        return result

    if n == 1 or concurrency <= 1:
        results = [one(i) for i in range(n)]
    else:
        with ThreadPoolExecutor(max_workers=min(concurrency, n)) as pool:
            results = list(pool.map(one, range(n)))

    return CaseResult(
        case_id=case.id,
        suite=suite.name,
        threshold=suite.threshold_for(case),
        results=results,
    )


def run_suites(suites: list[Suite], provider, concurrency: int = 4) -> RunResult:
    cases: list[CaseResult] = []
    for suite in suites:
        for case in suite.cases:
            cases.append(run_case(suite, case, provider, concurrency))
    model = getattr(provider, "model", "unknown")
    return RunResult(cases=cases, provider=provider.name, model=model)
