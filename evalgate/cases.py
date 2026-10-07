"""Loading suites from TOML.

Cases live in TOML rather than YAML for one reason: `tomllib` is in the
standard library and PyYAML is not. The core of this harness has no
dependencies, so it runs in CI without an install step and without a
requirements file that can drift.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class CaseError(ValueError):
    """A case file that cannot be loaded — fail loudly, never skip."""


@dataclass(frozen=True)
class Case:
    id: str
    prompt: str
    assertions: tuple[dict, ...]
    system: str | None = None
    samples: int | None = None
    min_pass_rate: float | None = None
    mock: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Suite:
    name: str
    path: Path
    cases: tuple[Case, ...]
    model: str = "claude-opus-5"
    effort: str = "medium"
    samples: int = 3
    min_pass_rate: float = 1.0

    def samples_for(self, case: Case) -> int:
        return case.samples if case.samples is not None else self.samples

    def threshold_for(self, case: Case) -> float:
        if case.min_pass_rate is not None:
            return case.min_pass_rate
        return self.min_pass_rate


def load_suite(path: Path) -> Suite:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise CaseError(f"{path}: {exc}") from exc

    meta = raw.get("suite", {})
    entries = raw.get("case", [])
    if not entries:
        raise CaseError(f"{path}: no [[case]] entries")

    cases: list[Case] = []
    seen: set[str] = set()
    for i, entry in enumerate(entries):
        cid = entry.get("id")
        if not cid:
            raise CaseError(f"{path}: case #{i + 1} has no 'id'")
        if cid in seen:
            raise CaseError(f"{path}: duplicate case id {cid!r}")
        seen.add(cid)

        prompt = entry.get("prompt")
        if not prompt:
            raise CaseError(f"{path}: case {cid!r} has no 'prompt'")

        asserts = entry.get("assert", [])
        if not asserts:
            raise CaseError(
                f"{path}: case {cid!r} has no [[case.assert]] — a case that "
                f"asserts nothing always passes and is worse than no case"
            )

        cases.append(
            Case(
                id=cid,
                prompt=prompt,
                assertions=tuple(asserts),
                system=entry.get("system"),
                samples=entry.get("samples"),
                min_pass_rate=entry.get("min_pass_rate"),
                mock=entry.get("mock", {}),
            )
        )

    return Suite(
        name=meta.get("name", path.stem),
        path=path,
        cases=tuple(cases),
        model=meta.get("model", "claude-opus-5"),
        effort=meta.get("effort", "medium"),
        samples=int(meta.get("samples", 3)),
        min_pass_rate=float(meta.get("min_pass_rate", 1.0)),
    )


def discover(target: Path) -> list[Suite]:
    """Load a single .toml file, or every .toml in a directory tree."""
    if target.is_file():
        return [load_suite(target)]
    paths = sorted(target.rglob("*.toml"))
    if not paths:
        raise CaseError(f"{target}: no .toml case files found")
    return [load_suite(p) for p in paths]
