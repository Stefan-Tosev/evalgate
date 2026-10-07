# evalgate

A regression gate for LLM features, built the way a test engineer would build it.

The premise is simple and, in most teams, unimplemented: **you cannot test a
non-deterministic system with one sample and a boolean.** The same prompt passes
four times and fails the fifth. A suite that runs each case once reports that as
a pass or a failure depending on which sample it happened to draw, and everyone
learns to ignore the result.

evalgate runs every case N times, reports a pass **rate**, and gates CI on
movement against a committed baseline rather than on an absolute score.

```
$ python -m evalgate cases/ --provider mock --seed 1

case                              status  rate    samples  latency
--------------------------------  ------  ------  -------  -------
absent-field-not-invented         PASS     100%   5/5        400ms
invoice-fields                    PASS     100%   5/5        850ms
invoice-total-arithmetic          FLAKY     80%   4/5       1100ms
                                    -> contains: missing '42.4'
no-refund-promise-outside-policy  PASS     100%   4/4       1900ms
no-refund-promise-under-pressure  FAIL      75%   3/4       2100ms
                                    -> not_contains: unexpectedly present: 'refund you'
reply-fits-the-widget             PASS     100%   4/4       1500ms

6 cases: 4 stable, 1 flaky, 1 failed · 2,069 tokens · mock/claude-opus-5

REGRESSIONS vs baseline:
  no-refund-promise-under-pressure: 100% -> 75% (-25%)
  invoice-total-arithmetic: 100% -> 80% (-20%)
```

Look at `invoice-total-arithmetic`. It **passes its own threshold** — 80% is the
declared bar for the extraction suite — and the run still fails, because it used
to be 100%. A threshold alone cannot tell you that; it can only tell you where
the floor is, never that you are falling towards it. That interaction is the
whole product.

Then look at the two suites' bars, which are deliberately not the same. Extraction
sets `min_pass_rate = 0.8`: a wrong invoice total is caught downstream by a human
who reconciles it. The support agent sets `1.0`: promising a refund outside policy
is not acceptable at *any* rate, because the one sample that does it is a
commitment the company has to honour. The threshold is a product decision, so it
lives in the case file, next to the prompt it judges — not in the runner.

## Run it

No dependencies, no install, no API key:

```bash
python -m evalgate cases/ --provider mock --seed 0    # green, matches the committed baseline
python -m unittest discover -s tests -t .             # 48 tests, no network
```

The mock provider is scripted from the case files themselves, so the flake
arithmetic, the thresholds, and the baseline gate are all exercised in CI without
spend. The seed picks which scripted draws come up: `--seed 0` is the clean run,
`--seed 1` draws the flake and the failure above. That is not a trick — it is the
same phenomenon the tool exists for, made reproducible.

Against a real model:

```bash
pip install anthropic
export ANTHROPIC_API_KEY=...
python -m evalgate cases/ --provider anthropic --samples 5
python -m evalgate cases/ --provider anthropic --update-baseline   # record
```

Exit codes: `0` clean, `1` a case failed its threshold or regressed, `2` the run
could not be performed (bad case file, missing provider). CI reads these.

### Flags

| Flag | Effect |
|---|---|
| `--provider mock\|anthropic` | which backend answers (default `mock`) |
| `--model` / `--effort` | override the suite file per run |
| `--samples N` | override samples per case |
| `--concurrency N` | parallel samples in flight (default 4) |
| `--baseline PATH` | where the committed baseline lives (default `baseline.json`) |
| `--update-baseline` | record this run *instead of* gating on it |
| `--tolerance F` | pass-rate drop treated as noise rather than regression |
| `--no-baseline` | skip the regression gate entirely |
| `--markdown PATH` | also write a markdown report, for CI artifacts |
| `--seed N` | make the mock provider's draws reproducible |

## Four states, not two

| State | Meaning |
|---|---|
| `PASS` | every sample passed — stable |
| `FLAKY` | some samples failed, but the pass rate clears the threshold |
| `FAIL` | the pass rate is below the threshold |
| `ERROR` | the provider raised, or the case file is malformed |

`FLAKY` exists because rounding it to either neighbour is a lie. A case at 4/5 is
a different engineering situation from one at 5/5 and from one at 2/5, and the
report says so.

`ERROR` is separated from `FAIL` for the same reason: a typo in an assertion is a
defect in the *suite*, and reporting it as a model failure sends somebody to
debug the wrong system.

## Writing a case

```toml
[suite]
name = "extraction"
model = "claude-opus-5"
samples = 5
min_pass_rate = 0.8      # 1 sample in 5 may fail

[[case]]
id = "invoice-fields"
system = "You extract structured data from documents. Return JSON only."
prompt = "Extract the vendor, invoice number, and total from: ..."

[[case.assert]]
type = "json_schema"
schema = { type = "object", required = ["vendor", "total"], properties = { vendor = { type = "string" }, total = { type = "number" } } }

[[case.assert]]
type = "contains"
value = "INV-4471"

[case.mock]                                   # only the mock provider reads this
response = '{"vendor": "Northwind", "total": 42.40}'
flake = '{"vendor": "Northwind", "total": 37.50}'
flake_rate = 0.2                              # scripted non-determinism
```

TOML rather than YAML for one reason: `tomllib` is in the standard library and
PyYAML is not. The core has no dependencies, so CI needs no install step and no
requirements file that can drift out of date.

A case with no assertions is a load error, not a pass. A suite that silently
asserts nothing is worse than no suite.

### Assertions

| Type | Checks |
|---|---|
| `contains` / `not_contains` | substring, optional `ignore_case` |
| `equals` | full match, `strip` on by default |
| `regex` | pattern search |
| `json_valid` | the output contains parseable JSON |
| `json_schema` | that JSON satisfies a schema (subset: `type`, `required`, `properties`, `items`, `enum`) |
| `max_latency_ms` | the sample came back in time |
| `max_output_tokens` | the reply fits its budget |
| `judge` | a second model grades the output against a rubric |

The JSON extractor pulls the first balanced object or array out of prose and code
fences, tracking string state so a `}` inside a string value doesn't end the
object early. Models wrap their JSON no matter what the prompt says; extracting
is honest, and a separate `not_contains` can assert that nothing surrounds it if
the contract demands raw JSON.

## In CI

`.github/workflows/eval.yml` runs two jobs, split on what each one costs:

- **`harness`** — unit tests plus the mock suite. No key, no network, no spend,
  so it gates every push including from forks. This is the job that proves the
  *tool* works.
- **`model`** — the live suite against a real model, with `--tolerance 0.2` and a
  markdown report uploaded as an artifact. Scoped to pull requests on the upstream
  repository, because it needs a secret and costs money; a fork PR cannot reach
  the key.

The split matters more than it looks. An eval suite that only runs when a
maintainer has a key is an eval suite that stops running.

## Design notes

**The baseline is committed and updated deliberately.** `--update-baseline` is a
separate invocation, so a regression can never be absorbed by a run that quietly
writes its own results back. A deleted case fails the gate too — otherwise the
cheapest way to fix a failing test is to delete it, and CI will help you.

**`--tolerance` is one sample's worth of noise.** At 4 samples, `--tolerance 0.25`
stops ordinary variance from paging someone at 3am. Zero is the default, because
the right value is a decision the team should make on purpose.

**Providers are a two-method interface** — `complete()` and `judge()`. The runner,
the assertions, and the baseline never learn which model they are testing. Adding
a provider is one module.

**A refusal is not a crash.** The Anthropic provider checks `stop_reason` before
touching `content`: a safety refusal returns HTTP 200 with an empty content array,
and indexing `content[0]` there would take down the run on exactly the inputs an
eval suite most wants to measure.

**Console output is ASCII, stdout is forced to UTF-8.** Model output is arbitrary
text; the console code page is not. This was found the honest way — the first run
on a cp1251 terminal died on a box-drawing character.

## Layout

```
evalgate/
  __main__.py     the CLI
  cases.py        loading and validating suites
  assertions.py   the checks, and a small JSON Schema subset
  runner.py       N samples -> one verdict
  baseline.py     the regression gate
  report.py       console and markdown
  providers/      mock (scripted) and anthropic (lazy import)
cases/            extraction.toml, support-agent.toml — runnable with no key
tests/            48 tests, stdlib unittest, no network
baseline.json     committed; the gate compares against this
.github/workflows/eval.yml
```

## What this is

A working answer to the question "how do you test something that gives a
different answer every time?" — which is the question every team shipping an LLM
feature has, and the one their existing test infrastructure cannot answer.

Built by Stefan Tosev — QA engineer, ISTQB and PSPO certified, four years in test
automation on industrial machine-communication interfaces.
