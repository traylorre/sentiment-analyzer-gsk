# Research: waitForResponse race regression guard

**Feature**: `002-waitforresponse-lint-guard` | **Date**: 2026-07-30

All findings checked against the working tree at `35d5f61` unless the entry says otherwise.

---

## R1 — Is there an upstream lint rule for this pattern?

**Question**: can an off-the-shelf rule detect act-then-wait `waitForResponse`?

**Finding**: no.

*Carried from 001's research, not re-verified here*: `eslint-plugin-playwright@2.11.0` ships 59
rules, none of which covers request-listener ordering. The nearest names,
`no-wait-for-navigation` and `no-wait-for-selector`, target deprecated APIs rather than the
act-then-wait shape.

*Verified here*: the published version is still `2.11.0` (`npm view eslint-plugin-playwright
version`), and the plugin is **not installed** — `frontend/node_modules/eslint-plugin-playwright`
does not exist.

**Decision**: no upstream option. Detection must be repo-owned.

**Secondary finding**: adopting the plugin wholesale is separately undesirable. 001's spec places it
Out of Scope because its default rule set would flag unrelated violations
(`no-conditional-in-test`, `no-networkidle`) across the existing suite, converting a targeted guard
into a suite-wide cleanup project.

---

## R2 — Would a custom ESLint rule actually run?

**Question**: if we wrote one, would it execute against `frontend/tests/e2e/*.spec.ts`?

**Finding**: **no**, and this is decisive.

Evidence chain:

1. `frontend/package.json:9` — `"lint": "next lint"`. This is the only lint script.
2. `frontend/.eslintrc.json` — a single `extends: "next/core-web-vitals"` line. No `overrides`, no
   `ignorePatterns`.
3. `frontend/next.config.js` — contains only `reactStrictMode` and `images`. No `eslint` block, so
   no `dirs` override.
4. No `--dir` argument anywhere in the npm scripts.
5. Therefore `next lint` falls through to Next.js's built-in default:
   `frontend/node_modules/next/dist/lib/constants.js:246-252` defines
   `ESLINT_DEFAULT_DIRS = ["app", "pages", "components", "lib", "src"]`.
6. `frontend/tests/` is not in that list.

**Consequence**: a custom rule would be authored, registered, committed, reviewed, and silently
never applied to a single file it was written for. It would present as working — `npm run lint`
exits 0 — while detecting nothing. That is the same failure shape the feature exists to prevent,
which makes it a particularly poor choice of mechanism.

**Additional friction, secondary to the above**: the frontend runs ESLint 8 with a legacy
`.eslintrc.json`. Local custom rules under legacy config require either a resolvable
`eslint-plugin-*` module, the `eslint-plugin-local-rules` shim, or `--rulesdir`, none of which
`next lint` exposes cleanly. This alone would not have been disqualifying; point 6 is.

**Decision**: defer editor-time feedback. Carded FR-011(b). Revisit if the lint invocation is ever
changed to cover `frontend/tests/`.

---

## R3 — Where should enforcement live so that it can actually block a merge?

**Question**: which CI job, if any, has the authority to stop a bad merge?

**Finding**: only three jobs do, and the obvious candidate is not among them.

```
gh api repos/traylorre/sentiment-analyzer-gsk/branches/main/protection \
  --jq '.required_status_checks.contexts'
→ ["Secrets Scan", "Lint", "Run Tests"]

gh api repos/traylorre/sentiment-analyzer-gsk/rulesets --jq 'length'
→ 0
```

The `pre-commit` job's display name is `Pre-commit Hooks` (`pr-checks.yml:192`). It is **absent**
from the required contexts and there are no rulesets supplying an alternative path. A red
`Pre-commit Hooks` job does not prevent `gh pr merge --auto --squash`, which is the merge command
CLAUDE.md documents.

**This inverted the design.** The Stage 1 draft asserted "the CI pre-commit job is a blocking gate"
on the strength of having read the workflow file. The workflow file describes what runs; branch
protection decides what matters. Reading one and concluding the other is the methodological error
at the centre of AR#1 finding F-01.

**Candidate hosts evaluated**:

| Host | Required? | Environment | Verdict |
|---|---|---|---|
| `Pre-commit Hooks` job | **No** | pre-commit 4.6.0, checkov, bc-detect-secrets, trivy; **no `.venv`** | Advisory only. Reached for free via the hook config, so keep it — but it cannot be the control. |
| `Lint` job | **Yes** | `actions/setup-python@v7`, `PYTHON_VERSION: '3.13'` (`:29`), installs only `ruff==0.15.14` | **Chosen.** Has a 3.13 interpreter, needs no new dependency for a stdlib-only script, and can block. |
| `Run Tests` job | Yes | Full `requirements-dev.txt` install | Would work, but it is the slowest job and this check needs no dependencies. Wrong altitude. |
| `Secrets Scan` job | Yes | gitleaks | Unrelated purpose. Rejected. |
| New dedicated job | — | — | Would require adding it to required contexts: a repo settings change, admin-gated. Same blocker as the alternative below. |
| Add `Pre-commit Hooks` to required contexts | — | — | Correct in the abstract, completes 1400 FR-007(b). Rejected here: admin rights needed, and it would retroactively make every hook merge-blocking, including `trivy-terraform`, documented as non-gating with 5 outstanding HIGH findings. Carded FR-011(f). |

**Decision**: `Lint` job step (blocking) **plus** the pre-commit hook (local feedback, and it rides
along in the advisory `Pre-commit Hooks` job at no cost).

---

## R4 — Does the CI runner have the project venv?

**Question**: can a hook invoke `.venv/bin/python3`, as the repo's existing pytest hook does?

**Finding**: **no**. `pr-checks.yml:211-221` installs `pre-commit==4.6.0`, `checkov==3.2.508`,
`bc-detect-secrets==1.5.45`, and the trivy binary. There is no `.venv`, no `requirements-*.txt`
install, and no bootstrap step.

The existing precedent is `.pre-commit-config.yaml:139`:

```yaml
- id: pytest
  entry: bash -c '.venv/bin/python3 -m pytest tests/unit -x --tb=short -q'
```

with the comment *"pre-commit runs in its own subprocess and doesn't inherit an activated venv"*.
That hook is `stages: [push]`, so it never runs in CI and its `.venv` dependency has never been
tested there.

**Consequence**: copying that entry form into a commit-stage hook would put the guard permanently
red in CI. Under R3's finding that the job is advisory, nobody would be blocked by it, so the
pressure would be to SKIP-list it — landing precisely on 1400 AR3-F2's forbidden outcome.

**Decision**: `entry: python3 scripts/scan-waitforresponse-race.py`, and require the detector be
stdlib-only (FR-005). Filed as a change request against 001 T001 criterion 8, which currently
specifies venv invocation. Venv invocation remains valid; venv *availability* must not be a
precondition.

---

## R5 — pre-commit stage semantics and the deprecation clock

**Question**: does `pre-commit run --all-files` run commit-stage hooks, and are the config's stage
names safe?

**Finding**: yes it does, and no they are not.

*Empirically confirmed during AR#1 across pre-commit `4.5.1`, `4.6.0`, and `4.6.1`*: under
`default_stages: [commit]` (`.pre-commit-config.yaml:36`), a stage-less hook runs under
`pre-commit run --all-files`; a `stages: [push]` hook does not. All three versions emit:

```
[WARNING] ... uses deprecated stage names ... which will be removed in a future version.
          run: `pre-commit migrate-config`
```

Three pins coexist: `4.6.1` (`requirements-dev.txt:37`, `requirements-ci.txt:58`), `4.6.0`
(`pr-checks.yml:218`), `4.5.1` (project `.venv`). Behaviour is identical across all three, so the
skew is harmless today and is recorded rather than fixed.

**Decision**: state `stages: [pre-commit]` explicitly on the new hook. It is valid on all three
installed versions and does not add to the deprecation debt. The config-wide migration
(`pre-commit migrate-config`) touches every hook in the file and is carded FR-011(e).

---

## R6 — What does a guard in this repo look like when it fails?

**Question**: are there worked examples of guards going inert here?

**Finding**: yes, one, and its authors documented it themselves.

`check-false-pass-patterns` (`.pre-commit-config.yaml:181-188`) is not in the CI `SKIP` list, so it
runs in the `pre-commit` job. It does nothing there. Its `--staged-only` branch reads
`git diff --cached --name-only --diff-filter=ACM` (`scripts/check-false-pass-patterns.sh:39-41`);
`actions/checkout` leaves the index matching `HEAD`, so the diff is empty and it prints
`No test files to check` and exits 0 (`:47-49`).

Feature 1400 wrote this down in the job's own `env:` block at `pr-checks.yml:236-240`:

> *"check-false-pass-patterns uses --staged-only and thus NO-OPS in CI (nothing is staged) — it
> gates local commits only; not claimed as CI coverage here (honesty, per this feature's whole
> point)."*

**Second axis, not covered by that note**: the script's filter is `^tests/.*\.py$` (`:41`) and its
non-staged branch is `find tests/e2e -name "*.py"` (`:44`). Both target the **admin** pytest suite.
It could never have covered `frontend/tests/e2e/*.ts` under any invocation, so its scope was never
this class of defect either.

**Third example, adjacent**: `check-error-log-assertions` (`:170-177`) is `stages: [push]`. It looks
like a structural twin of `check-false-pass-patterns` but fires on neither `git commit` nor
`pre-commit run --all-files`. `pr-checks.yml:236-238` says so explicitly.

**Generalised failure taxonomy** — a guard in this repo can be present, unskipped, green, and inert
via any of:

| Axis | Example | Countered by |
|---|---|---|
| Invocation mode | `--staged-only` on an empty CI index | FR-003 whole-tree scan (`pass_filenames: false`, `always_run: true`) |
| Scan scope | filter targets the wrong suite | `contracts/detector-cli.md` C5 pins the scan root |
| Hook stage | `stages: [push]` never runs on commit or `--all-files` | FR-003 forbids it |
| Runtime environment | `.venv/bin/python3` absent on the runner | FR-005 stdlib-only, bare `python3` |
| Job authority | job is not a required status check | FR-004 uses the required `Lint` job |
| Empty target | scan root renamed, zero files, exit 0 | FR-013 non-zero on zero files |

**Decision**: FR-007's four verification modes plus SC-011’s rename test cover all six rows. This
taxonomy is the feature's actual contribution; the YAML is incidental.

---

## R7 — Scan cost

**Question**: is a whole-tree scan on every commit affordable?

**Finding**: the scan root holds **47** `.ts` files (`find frontend/tests/e2e -name "*.ts" | wc -l`),
of which 6 contain `waitForResponse` or `waitForEvent` matches. A naive
`grep -rn "waitForResponse\|waitForEvent"` over the root returns 41 lines, 7 of which are comments,
leaving 34 real call sites (001 T001 criterion 4).

The Stage 1 draft asserted "roughly ten files", which was wrong by roughly 5x and was an estimate
presented as a fact in a section claiming verification.

**Decision**: no estimate. SC-010 requires a **measured** figure with a 2-second budget, so the
criterion can fail rather than being satisfied by assertion.
