# Untested

Append-only. One line per skip: date, what is untested, what it would
have caught. Cleared by marking it cleared with a date, never by deleting.

- 2026-10-07 — `.github/workflows/eval.yml` has never run; the repo had no
  git until today. Would catch: a broken CI config the README describes as
  working. **Cleared 2026-10-07** — first push, `harness` job green:
  https://github.com/Stefan-Tosev/evalgate/actions/runs/37612676521
- 2026-10-07 — the `model` job (live Anthropic provider) has never run;
  needs `ANTHROPIC_API_KEY` as a repo secret. Would catch: the real
  provider drifting from the mock's interface.
