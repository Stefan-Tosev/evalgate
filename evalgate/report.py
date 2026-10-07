"""Rendering a run — for a terminal, and for a pull request comment."""

from __future__ import annotations

from .baseline import Comparison
from .runner import ERROR, FAILED, FLAKY, STABLE, RunResult

_MARK = {STABLE: "PASS", FLAKY: "FLAKY", FAILED: "FAIL", ERROR: "ERROR"}


def console(result: RunResult, comparison: Comparison | None = None) -> str:
    lines: list[str] = []
    width = max((len(c.case_id) for c in result.cases), default=4)
    width = max(width, 4)

    lines.append(f"{'case'.ljust(width)}  status  rate    samples  latency")
    lines.append(f"{'-' * width}  ------  ------  -------  -------")

    for c in sorted(result.cases, key=lambda c: (c.suite, c.case_id)):
        # Built as parts, not adjacent f-string literals: Python concatenates
        # those at compile time, so a trailing .ljust() would pad the whole
        # row instead of the one column it was meant for.
        samples = f"{c.passes}/{c.samples}"
        lines.append(
            "  ".join(
                (
                    c.case_id.ljust(width),
                    _MARK[c.status].ljust(6),
                    f"{c.pass_rate:5.0%} ",
                    samples.ljust(7),
                    f"{c.mean_latency_ms:5.0f}ms",
                )
            )
        )
        if c.status in (FAILED, ERROR, FLAKY):
            detail = c.first_failure()
            if detail:
                # ASCII only: this line lands on whatever code page the
                # terminal happens to be (cp1251 here), and a box-drawing
                # character would crash the run rather than the eval failing.
                lines.append(f"{' ' * width}    -> {detail}")

    stable = sum(1 for c in result.cases if c.status == STABLE)
    flaky = sum(1 for c in result.cases if c.status == FLAKY)
    failed = sum(1 for c in result.cases if c.status in (FAILED, ERROR))
    lines.append("")
    lines.append(
        f"{len(result.cases)} cases: {stable} stable, {flaky} flaky, {failed} failed "
        f"· {result.total_tokens:,} tokens · {result.provider}/{result.model}"
    )

    if comparison is not None:
        lines.append("")
        lines.append(_drift_lines(comparison))

    return "\n".join(lines)


def _drift_lines(comparison: Comparison) -> str:
    out: list[str] = []
    if comparison.regressions:
        out.append("REGRESSIONS vs baseline:")
        for d in comparison.regressions:
            out.append(f"  {d.case_id}: {d.before:.0%} -> {d.after:.0%} ({d.delta:+.0%})")
    if comparison.removed:
        out.append("MISSING vs baseline (case deleted or renamed):")
        out.extend(f"  {cid}" for cid in comparison.removed)
    if comparison.improvements:
        out.append("Improvements:")
        for d in comparison.improvements:
            out.append(f"  {d.case_id}: {d.before:.0%} -> {d.after:.0%} ({d.delta:+.0%})")
    if comparison.added:
        out.append(f"New cases (not yet in baseline): {', '.join(comparison.added)}")
    if not out:
        out.append("No drift against baseline.")
    return "\n".join(out)


def markdown(result: RunResult, comparison: Comparison | None = None) -> str:
    lines = ["# Eval run", ""]
    stable = sum(1 for c in result.cases if c.status == STABLE)
    flaky = sum(1 for c in result.cases if c.status == FLAKY)
    failed = sum(1 for c in result.cases if c.status in (FAILED, ERROR))
    lines.append(
        f"`{result.provider}/{result.model}` — **{stable} stable, {flaky} flaky, "
        f"{failed} failed** across {len(result.cases)} cases "
        f"({result.total_tokens:,} tokens)."
    )
    lines += ["", "| case | status | pass rate | samples | mean latency | first failure |",
              "|---|---|---|---|---|---|"]
    for c in sorted(result.cases, key=lambda c: (c.suite, c.case_id)):
        detail = c.first_failure().replace("|", "\\|")
        lines.append(
            f"| `{c.case_id}` | {_MARK[c.status]} | {c.pass_rate:.0%} | "
            f"{c.passes}/{c.samples} | {c.mean_latency_ms:.0f}ms | {detail} |"
        )

    if comparison is not None:
        lines += ["", "## Drift", "", "```", _drift_lines(comparison), "```"]

    return "\n".join(lines) + "\n"
