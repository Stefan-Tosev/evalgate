# NEXT

**Updated:** 16 August 2026

## Where things stand

The harness is complete and working. 48 unit tests pass, no network, no
dependencies outside the standard library. `--seed 0` runs green against the
committed baseline and exits 0; `--seed 1` demonstrates the flake and the
regression gate and exits 1.

The README was rewritten this session. Its demo block had drifted — it showed
output from a run that no longer produces those numbers. It is now byte-for-byte
the real output of `python -m evalgate cases/ --provider mock --seed 1`, verified
by diff. Also added: a flags table, a CI section, and the point that the two
suites carry deliberately different bars (extraction `0.8`, support-agent `1.0`).

## The single next action

**`git init`, commit, and push to GitHub.**

This is not housekeeping. The repo is the portfolio piece the CV points at, and
right now the link on the CV goes nowhere. Everything else is finished; this is
the only thing standing between the work and anyone seeing it.

## Traps for the next session

- **This is not a git repository.** No `.git`, no remote, no history — despite
  `.github/workflows/eval.yml` sitting in the tree. **The CI workflow has
  therefore never run once.** The README describes its two-job split as though it
  operates. That is true of the file, not of any actual run. Push it, watch the
  first `harness` job go green, and only then treat that section as evidence.
- **The `model` job needs `ANTHROPIC_API_KEY` as a repo secret** or it will fail
  on the first pull request. It is scoped to upstream PRs only, so it will not
  fire on the initial push — but it will the first time a PR is opened.
- **`baseline.json` is committed on purpose** and is excluded from `.gitignore`
  explicitly. Do not "tidy" it away; the regression gate has nothing to compare
  against without it.
- **The README's demo output is verified, not illustrative.** If the case files,
  the mock scripting or the report formatting change, that block goes stale
  silently. Re-diff it against a real `--seed 1` run before publishing changes.
  A portfolio repo whose own README does not match its output undercuts the one
  argument the project makes.
- **Console output is ASCII deliberately.** The first run on a cp1251 terminal
  died on a box-drawing character. Do not reintroduce box-drawing or emoji in
  `report.py`.

## Needs Stefan, not the assistant

- Whether this goes public on GitHub under the account linked from the CV, and
  under what name. The CV currently lists `[github.com/Stefan-Tosev]` in square
  brackets — an unverified placeholder.
- Adding `ANTHROPIC_API_KEY` to the repo secrets, if the live job is wanted.

## Deliberately not done

- **No packaging** — no `pyproject.toml`, no PyPI. `python -m evalgate` with zero
  dependencies is the point; an install step would weaken the strongest claim the
  README makes.
- **No second provider.** The two-method interface is demonstrated by mock plus
  anthropic. A third adds surface without adding argument.
