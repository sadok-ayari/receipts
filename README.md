# receipts

Check a README's claims against the repository that makes them.

```
$ receipts audit .
4 claims · 4 supported · 0 unsupported · 0 unverifiable
```

```
$ receipts audit ../some-repo
7 claims · 4 supported · 3 unsupported · 0 unverifiable
  line 9: '68 tests' — 12 test functions
  line 14: 'No dependencies' — requests (tool/fetch.py)
  line 3: 'CI is green' — no workflow file
```

## Why

A README is a marketing document written by the person who wants it to be true. Reviewers read the status table and the test count and take both on faith. In practice, repositories that announce more than they ship accumulate claims faster than they accumulate tests, and nobody checks, because checking means running the suite and counting.

Receipts reads the claims, then checks them against the working tree: test functions by AST, licence file, declared Python floor, imports against the stdlib, CI workflow presence, and whether the "shipped" label has history, tests and CI behind it.

**A claim with no evidence is not a small thing.** It is the difference between a demo and a deliverable, and it is the first thing a technical counterparty checks.

## What it checks

| Claim | Check |
|---|---|
| `68 tests`, `24 offline tests` | test functions found by AST across the tree |
| `MIT`, `Apache-2.0` | licence file exists and names the same licence |
| `No dependencies`, `stdlib only` | every top-level import resolves to the standard library |
| `Python 3.9+` | `requires-python` in `pyproject.toml` |
| `CI is green` | a workflow file exists (run status needs the network, so it is not asserted) |
| `Shipped`, `stable`, `v1.0.0 released` | commits, tests and a workflow present |

Three verdicts: `supported`, `unsupported`, `unverifiable`. Unverifiable is used when the check cannot see enough (no `pyproject.toml`, not a git repository) and is never reported as a pass.

## Install

Python 3.9+. No dependencies, and it audits itself to prove it.

```bash
git clone https://github.com/sadok-ayari/receipts.git
cd receipts
python -m receipts audit .
```

## Use it in CI

```yaml
- name: Every claim in the README must hold
  run: python -m receipts audit . --strict
```

`--strict` also fails on unverifiable claims, which is what you want on your own repository and not on a repository you are reviewing.

## Output

Markdown with one row per claim, plus a "fix or withdraw" list for each failure. `--json` for a scheduler or a dashboard. Exit `1` on any unsupported claim, `2` when there is no README.

## How this lands in a working week

- **Ritual:** the release step. Nothing gets a version tag and a status table until `audit` exits 0.
- **Trigger:** pre-push hook, or the CI job that already runs the tests.
- **Format:** one number in the build log. A failure names the line and the gap.
- **Owner:** whoever cuts the release.
- **Fail state:** a claim that has been unsupported for two releases is deleted, not reworded.

## Honest limits

- **It reads strings, not meaning.** A claim phrased in a way the patterns miss is not checked at all. Silent by omission, not by design.
- **Test functions are not test cases.** One function with a loop over forty inputs counts once. The number is a floor, never a ceiling.
- **No network.** "CI is green" is checked as "a workflow exists". The run status is deliberately not fetched: no credentials, no rate limits, no flaky audits.
- **Its own blind spot.** The parser only understands claims it was written to see. Adding a claim type means adding a pattern and a check, in that order.

## Tests

27 tests, all offline. The number is checked by this tool before every commit. Note the
fenced block below: what a README demonstrates is not a claim, which is why it is skipped.

```bash
python -m unittest discover -s tests   # 27 tests, offline
```

## Licence

MIT. See [LICENSE](LICENSE).
