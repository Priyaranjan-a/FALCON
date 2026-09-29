# Contributing to FALCON

Thank you for taking an interest. FALCON is built by **Team THETA172** for
Smart India Hackathon problem statement 26164, and we welcome issues, ideas and
pull requests.

## Ways to help

| | |
|---|---|
| **Report a bug** | [Open a bug report](https://github.com/shriomverma100/FALCON/issues/new?template=bug_report.yml). Tell us what you expected and what happened, with the steps to reproduce. |
| **Suggest a feature** | [Open a feature request](https://github.com/shriomverma100/FALCON/issues/new?template=feature_request.yml). |
| **Report a vulnerability** | Please do **not** open a public issue. See [SECURITY.md](SECURITY.md). |
| **Improve the detectors** | New rules for a language or library are the most valuable contribution: see below. |

## Set up your environment

Needs Python 3.12+ and Node.js 20.19+ (or 22.12+).

```sh
git clone https://github.com/shriomverma100/FALCON.git
cd FALCON
sh scripts/setup.sh          # or: powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

For day-to-day work, `scripts/dev.ps1` runs the API with auto-reload and the
console with hot reload at <http://127.0.0.1:5180>.

## Before you open a pull request

Everything must pass:

```sh
cd server  && .venv/bin/python -m pytest            # 326 tests (.venv/Scripts/python on Windows)
cd console && npx tsc -b && npx vitest run && npm run build
```

CI runs the same checks on Linux, so a green run locally means a green run there.

### What we look for

- **A test that fails without your change.** For a bug fix, write the test
  first and confirm it reproduces the problem.
- **Changes to behaviour are documented.** Update the README and the relevant
  file in `docs/`.
- **Comments explain *why*, not *what*.** The code says what it does.
- **British English** in user-visible text and documentation, to match the
  rest of the project.
- **No new dependencies** without a good reason. FALCON runs in air-gapped
  networks, so every dependency is a liability.

## Adding a detection rule

Most new cryptography is recognised by adding to the knowledge bases, with no
code change:

| File | Holds |
|---|---|
| `server/falcon/knowledge/algorithms.json` | Algorithms, parameters, strength and quantum assessment |
| `server/falcon/knowledge/libraries.json` | Libraries, their post-quantum readiness and end-of-life dates |
| `server/falcon/knowledge/rules/*.json` | Per-language pattern rules (259 across 11 packs) |
| `server/falcon/knowledge/pqc.json` | Post-quantum replacements and their FIPS sizes |
| `server/falcon/knowledge/risk.json` | Scoring weights, migration effort and framework dates |

A rule needs a literal `gate` so the prefilter can skip files that cannot
match, and a test in `server/tests/test_discovery_engine.py` proving it fires
on a fixture and does not fire elsewhere. Add the sample to
`fixtures/estates/` (synthetic material only, never real keys or certificates).

## Commit messages

Write a short imperative summary, then a paragraph explaining *why*:

```
Reject archives whose members escape the extraction root

A crafted tar could write outside the workspace through ../ members and
absolute paths. Members are now resolved against the root and skipped when
they escape it, with a test covering both forms.
```

## Code of conduct

Participation is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Licence

Contributions are accepted under the [MIT Licence](LICENSE).
