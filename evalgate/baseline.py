"""The regression gate.

A pass/fail suite tells you whether the system is good. A baseline tells you
whether it got *worse*, which is the question CI actually needs answered — and
the one a threshold alone cannot answer, because a case sitting at 0.8 against
a 0.8 threshold is passing whether it used to be 0.8 or 1.0.

The baseline is a committed file. Updating it is an explicit act
(`--update-baseline`), so a regression can never be absorbed silently by a run
that happens to write its own results back.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .runner import RunResult

FORMAT_VERSION = 1


@dataclass(frozen=True)
class Drift:
    case_id: str
    before: float
    after: float

    @property
    def delta(self) -> float:
        return self.after - self.before


@dataclass(frozen=True)
class Comparison:
    regressions: list[Drift]
    improvements: list[Drift]
    added: list[str]
    removed: list[str]

    @property
    def clean(self) -> bool:
        return not self.regressions and not self.removed


def snapshot(result: RunResult) -> dict:
    return {
        "format": FORMAT_VERSION,
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "provider": result.provider,
        "model": result.model,
        "cases": {
            c.case_id: {
                "pass_rate": round(c.pass_rate, 4),
                "samples": c.samples,
                "threshold": c.threshold,
                "status": c.status,
            }
            for c in sorted(result.cases, key=lambda c: c.case_id)
        },
    }


def write(path: Path, result: RunResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot(result), indent=2) + "\n", encoding="utf-8")


def read(path: Path) -> dict | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != FORMAT_VERSION:
        raise ValueError(
            f"{path}: baseline format {data.get('format')!r} is not {FORMAT_VERSION}; "
            f"re-record it with --update-baseline"
        )
    return data


def compare(result: RunResult, previous: dict, tolerance: float = 0.0) -> Comparison:
    """Diff a run against a recorded baseline.

    `tolerance` is the drop in pass rate treated as noise rather than
    regression. Zero is the strict default; on a small sample count a
    tolerance of one sample's worth (1/N) avoids flagging ordinary variance.
    """
    old = previous.get("cases", {})
    new = result.by_id()

    regressions: list[Drift] = []
    improvements: list[Drift] = []

    for case_id, current in new.items():
        if case_id not in old:
            continue
        before = float(old[case_id]["pass_rate"])
        after = current.pass_rate
        if after < before - tolerance:
            regressions.append(Drift(case_id, before, after))
        elif after > before:
            improvements.append(Drift(case_id, before, after))

    return Comparison(
        regressions=sorted(regressions, key=lambda d: d.delta),
        improvements=sorted(improvements, key=lambda d: -d.delta),
        added=sorted(set(new) - set(old)),
        removed=sorted(set(old) - set(new)),
    )
