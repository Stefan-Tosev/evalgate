# NEXT

**Updated:** 7 October 2026

## Where things stand

Finished and on GitHub, **private**: https://github.com/Stefan-Tosev/evalgate.
48 unit tests pass locally; the CI `harness` job ran green on the first push
(https://github.com/Stefan-Tosev/evalgate/actions/runs/37612676521). The
`model` job was skipped, as designed — it only fires on pull requests.

Context: Stefan is applying for an internal AI role at Liebherr, moving from
QA. This repo is the portfolio piece for that — QA for LLM outputs.

## The single next action

**Stefan reads the README on GitHub as a hiring manager would, then switches
the repo to public** (Settings → General → Danger Zone:
https://github.com/Stefan-Tosev/evalgate/settings). Public is irreversible —
see the list in `CLAUDE.md`.

## Traps for the next session

- **The `model` job has never run.** It needs `ANTHROPIC_API_KEY` as a repo
  secret and fails on the first pull request without one. Logged in
  `docs/untested.md`.
- **`baseline.json` is committed on purpose.** Do not "tidy" it away; the gate
  has nothing to compare against without it. Changing it is irreversible work.
- **The README's demo output is verified, not illustrative.** It is the exact
  output of `python -m evalgate cases/ --provider mock --seed 1`. Changing
  cases, mock scripting or report formatting stales it silently — re-diff.
- **Console output is ASCII deliberately** (cp1251 terminal crashed on a
  box-drawing character). No box-drawing or emoji in `report.py`.
- **The CV still shows the GitHub link in square brackets** — unverified.
  It is now real: https://github.com/Stefan-Tosev/evalgate. Update the CV once
  public.

## Needs Stefan, not the assistant

- The public switch.
- Adding `ANTHROPIC_API_KEY` to repo secrets, if the live job is wanted.

## Deliberately not done

- **No packaging** — zero-dependency `python -m evalgate` is the point.
- **No second provider** — mock plus anthropic demonstrates the interface.
