"""The CLI, and the exit codes CI reads.

    0  every case cleared its threshold and nothing regressed
    1  a case failed its threshold, or a case regressed against the baseline
    2  the run could not be performed (bad case file, missing provider)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import baseline as baseline_mod
from . import report
from .cases import CaseError, discover
from .providers import build_provider
from .runner import run_suites

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_BROKEN = 2


def _force_utf8_stdout() -> None:
    """Model output is arbitrary text; the console code page is not.

    On a non-UTF-8 console (cp1251 here) a single Cyrillic character in a
    failure detail would raise UnicodeEncodeError and take down the whole run.
    Losing a character to a replacement glyph is the right trade.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover - platform dependent
            pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8_stdout()
    parser = argparse.ArgumentParser(prog="evalgate", description=__doc__)
    parser.add_argument("target", type=Path, help="a .toml case file, or a directory of them")
    parser.add_argument("--provider", default="mock", choices=("mock", "anthropic"))
    parser.add_argument("--model", default=None, help="override the model in the suite file")
    parser.add_argument("--effort", default=None, choices=("low", "medium", "high", "xhigh", "max"))
    parser.add_argument("--samples", type=int, default=None, help="override samples per case")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--baseline", type=Path, default=Path("baseline.json"))
    parser.add_argument("--update-baseline", action="store_true",
                        help="record this run as the new baseline instead of gating on it")
    parser.add_argument("--tolerance", type=float, default=0.0,
                        help="pass-rate drop treated as noise rather than regression")
    parser.add_argument("--no-baseline", action="store_true", help="skip the regression gate entirely")
    parser.add_argument("--markdown", type=Path, default=None, help="also write a markdown report here")
    parser.add_argument("--seed", type=int, default=None, help="mock provider seed")
    args = parser.parse_args(argv)

    try:
        suites = discover(args.target)
    except CaseError as exc:
        print(f"evalgate: {exc}", file=sys.stderr)
        return EXIT_BROKEN

    if args.samples is not None:
        suites = [
            type(s)(**{**s.__dict__, "samples": args.samples}) for s in suites
        ]

    model = args.model or suites[0].model
    effort = args.effort or suites[0].effort
    try:
        provider = build_provider(args.provider, model=model, effort=effort, seed=args.seed)
    except Exception as exc:  # noqa: BLE001
        print(f"evalgate: {exc}", file=sys.stderr)
        return EXIT_BROKEN

    result = run_suites(suites, provider, concurrency=args.concurrency)

    comparison = None
    if not args.no_baseline and not args.update_baseline:
        try:
            previous = baseline_mod.read(args.baseline)
        except ValueError as exc:
            print(f"evalgate: {exc}", file=sys.stderr)
            return EXIT_BROKEN
        if previous is not None:
            comparison = baseline_mod.compare(result, previous, tolerance=args.tolerance)

    print(report.console(result, comparison))

    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(report.markdown(result, comparison), encoding="utf-8")
        print(f"\nwrote {args.markdown}")

    if args.update_baseline:
        baseline_mod.write(args.baseline, result)
        print(f"\nbaseline recorded at {args.baseline}")
        return EXIT_OK

    if not result.passed:
        return EXIT_FAILED
    if comparison is not None and not comparison.clean:
        return EXIT_FAILED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
