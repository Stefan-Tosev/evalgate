# evalgate

A regression gate for LLM outputs. Standard library only; `python -m
evalgate`. See `README.md` for what it does and `NEXT.md` for state.

## The irreversible list

Named 7 October 2026, on `git init`. Re-read and extended at every phase
boundary, in the same session as the ledger (`docs/untested.md`).

**If a diff touches one of these, it is irreversible work** and needs
domain-level tests that re-run in seconds without network.

1. **the gate's verdict** — the exit code from `__main__.py` and the
   pass/fail logic in `assertions.py` and `baseline.py`. A gate that wrongly
   passes ships a bad release silently; nobody looks at a green check.
2. **`baseline.json`** — what "no regression" is measured against.
   Accepting a worse baseline turns every later regression into a pass.
   Changing it is a decision, not a refresh, and goes in its own commit.
3. **public git history** — once pushed to a public GitHub repo it is
   cloned, cached and indexed. Rewriting history does not retract it.
4. **`ANTHROPIC_API_KEY`** — lives only in the environment and in GitHub
   repo secrets. Never in a file, a case, a report or a commit. Secrets in
   history are permanent; rotation would not retire them.

`cases/`, `report.py` and the mock provider are ordinary — but the README
demo block is a byte-for-byte copy of `--seed 1` output, so changing them
means re-diffing the README.
