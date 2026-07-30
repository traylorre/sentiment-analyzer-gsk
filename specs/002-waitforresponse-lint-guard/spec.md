# Feature Specification: waitForResponse race regression guard

**Feature Branch**: `002-waitforresponse-lint-guard`
**Created**: 2026-07-30
**Status**: Draft
**Depends on**: `001-waitforresponse-race-sweep` (hard dependency — see Context)
**Input**: Add a repository guard that prevents reintroduction of the act-then-wait `waitForResponse`
race pattern in Playwright E2E tests, enforced in both pre-commit and CI.

## Context

Feature 001 converts 27 racy `waitForResponse` / `waitForEvent` call sites in
`frontend/tests/e2e/` from act-then-wait to promise-first. It fixes the sites that exist today. It
does nothing about the 28th.

The interesting question is not "how did 27 sites become racy" but "how did 27 sites become racy
without anything noticing". The answer is that nothing was looking. The pattern is legal
TypeScript, `tsc` accepts it, no lint rule in this repo examines it, and it reads naturally
top-to-bottom in review. It fails only under load, in CI, in **5 of the 25 sampled PR-Checks runs
where Playwright executed** (001 spec, "Confirmed CI failures"). That ~20% figure describes *runs*,
not commits, and 001 states it that way deliberately. Every one of those 27 sites was written by
someone who believed they were writing a correct test, and they were all correct in the only ways
the toolchain could measure.

So 001 pays down the debt and 002 stops it re-accruing. This feature adds the missing detector to
the gate.

### The dependency is not stylistic

002 cannot land before 001. A guard that gates on "zero racy sites" would, on the pre-001 tree,
fail immediately on all 27 existing violations. Landing it there would either block every commit in
the repository or force it to ship with a suppression list, and a guard that ships pre-suppressed
is the thing it was meant to prevent.

This is settled repo doctrine, not a judgment call. The `trivy-terraform` hook in
`.pre-commit-config.yaml:111-124` carries an in-line record of the same decision: Feature 1400
intended to flip it to `--exit-code 1`, found 5 pre-existing HIGH findings, and left it non-gating
with a `TODO` rather than born-red the gate. The comment's own words are *"Flipping now would
born-red the pre-commit gate, violating the 'land green first' rule (FR-007)"* (`:114-115`) and
*"Escape hatch per AR3-F2: never regress to decorative once green"* (`:117`).

1400's FR-007 is worth quoting precisely, because its second clause is the one this feature nearly
repeated. `specs/1400-validator-gating/spec.md:77-80` requires a gate to land **in two steps**:
*"(a) job added and observed green on main (baseline must be clean BEFORE the job exists) … then
(b) job marked as a required status check."* Step (b) is not decoration. See the next section.

### What 001 hands over

001 commits `scripts/scan-waitforresponse-race.py` (001 task T001) as a runnable artifact. It is
already shaped as a guard's hook point, and was specified that way deliberately:

| Property (001 T001 acceptance criteria) | Why 002 depends on it |
|---|---|
| Scans every `*.ts` under `frontend/tests/e2e/`, spec files **and** `helpers/` | The scan root is already the right one |
| Classifies **both** `page.waitForResponse(...)` and `page.waitForEvent('requestfailed'\|'response')` | The method-name-only framing is what hid 3 of the 27 sites (001 AR#2 N-01) |
| Documents the classification rule in its own module docstring | The rule is auditable without reading the parser |
| Excludes comment lines from the call-site population (34 real sites, not the naive grep's 41) | A guard that counts comments produces false positives and gets disabled |
| Adjacency rule: an intervening statement makes a site `OTHER`, not `RACY` | Verified against `chaos-scenarios.spec.ts:138` |
| Prints `OTHER` sites under an explicit "requires human triage" banner | A shape the classifier cannot place stays visible instead of counting as clean by omission |
| `sys.exit(1)` when `RACY > 0`, `sys.exit(0)` otherwise | This is the entire gating contract, already implemented |

001 clarification **C4** (`001/spec.md:509-515`) states the split explicitly: the scan is committed
as a runnable artifact only, is deliberately **not** wired into pre-commit or any workflow, and
enforcement belongs to this feature. 001 task T001 criterion 9 asserts that
`grep -rn "scan-waitforresponse-race" .pre-commit-config.yaml .github/` returns nothing. This
feature makes that grep return something.

**The detector does not exist yet.** Every task in `001/tasks.md` is unchecked. 002 is therefore
specifying against an interface that has been described but never executed, which is why FR-012
pins that interface down as an explicit contract rather than discovering it during verification.

### Verified facts about the enforcement surface

Each bullet names its evidence source. Items checked against the working tree at `35d5f61` say so;
items carried from 001's research say that instead.

- **No upstream rule exists.** *Source: 001 research, not re-verified here.* 001's spec records that
  `eslint-plugin-playwright@2.11.0` ships 59 rules and none covers this pattern, the nearest
  neighbours (`no-wait-for-navigation`, `no-wait-for-selector`) being about deprecated APIs rather
  than ordering. *Checked at `35d5f61`:* the package version is current
  (`npm view eslint-plugin-playwright version` → `2.11.0`) and the plugin is **not installed**
  (`frontend/node_modules/eslint-plugin-playwright` does not exist). 001 places adopting it
  wholesale in Out of Scope because it would flag unrelated violations (`no-conditional-in-test`,
  `no-networkidle`) suite-wide.
- **The frontend lint invocation cannot see the target files.** *Checked at `35d5f61`.*
  `frontend/package.json:9` defines `"lint": "next lint"`. `frontend/.eslintrc.json` carries a
  single `extends` line and nothing else. There is no `--dir` argument and no `eslint` block in
  `frontend/next.config.js`, so `next lint` falls back to Next.js's `ESLINT_DEFAULT_DIRS`, which is
  `["app", "pages", "components", "lib", "src"]`
  (`frontend/node_modules/next/dist/lib/constants.js:246-252`). `frontend/tests/` is not in that
  list. A custom ESLint rule added today would be committed, configured, and never executed against
  a single file it was written for.
- **The repo already guards frontend E2E test files.** *Checked at `35d5f61`.* `make validate`
  depends on `check-test-target-headers` (`Makefile:42`), whose recipe (`:45-54`) greps
  `frontend/tests/e2e/*.spec.ts` **and** `tests/e2e/test_*.py` for a `Target:` header. Repo-level
  guards over this exact directory are established practice.
- **The `Lint` job is a required status check; the `Pre-commit Hooks` job is not.** *Checked at
  `35d5f61` via the GitHub API.*
  `repos/traylorre/sentiment-analyzer-gsk/branches/main/protection` reports
  `required_status_checks.contexts` = `["Secrets Scan", "Lint", "Run Tests", "Playwright E2E Tests"]`, and
  `repos/.../rulesets` is empty. The `pre-commit` job's display name is `Pre-commit Hooks`
  (`pr-checks.yml:192`), which is absent from that list. **A red `Pre-commit Hooks` job does not
  block a merge**, and CLAUDE.md's documented workflow is `gh pr merge --auto --squash`, which waits
  only on required checks. 1400 FR-007 step (b) has not been performed for this job.

  **Re-verified 2026-07-30 at implementation time, and the list had changed.** When this spec was
  authored the contexts were `["Secrets Scan", "Lint", "Run Tests"]`. `"Playwright E2E Tests"` was
  added as a fourth after PR #985 split the Playwright suite into a blocking job and a non-blocking
  chaos job; the chaos job is deliberately not required. Every count and list in this feature's
  artifacts has been updated to four. The load-bearing fact is unchanged: `Lint` is required and
  `Pre-commit Hooks` is not, so FR-004's placement decision stands on the same reasoning it always
  did. Recorded rather than silently corrected, because a spec whose pinned evidence drifts without
  comment is indistinguishable from one that was never checked. Re-check with:
  `gh api repos/traylorre/sentiment-analyzer-gsk/branches/main/protection --jq '.required_status_checks.contexts'`
  (rulesets still `0`).
- **The required `Lint` job can host the detector as-is.** *Checked at `35d5f61`.*
  `pr-checks.yml:35-65` runs `actions/setup-python@v7` with `PYTHON_VERSION: '3.13'` (`:29`) and
  then `pip install ruff==0.15.14`. It has a Python 3.13 interpreter on `PATH` and installs nothing
  else. A stdlib-only script runs there with no new dependency.
- **The CI `pre-commit` job installs no project dependencies.** *Checked at `35d5f61`.*
  `pr-checks.yml:211-221` installs `pre-commit==4.6.0`, `checkov`, `bc-detect-secrets`, and the
  trivy binary. There is **no `.venv`** on the runner and no `requirements-*.txt` install. The
  repo's only Python-invoking local hook is `pytest` (`.pre-commit-config.yaml:139`), wired as
  `entry: bash -c '.venv/bin/python3 -m pytest …'` and carrying the comment *"pre-commit runs in its
  own subprocess and doesn't inherit an activated venv"*. That hook is `stages: [push]`, so it never
  runs in CI. Copying its `.venv/bin/python3` entry form into a commit-stage hook would put the
  guard permanently red in CI.
- **Two local pre-commit hooks look like a structural template; only one of them is.** *Checked at
  `35d5f61`.* `check-error-log-assertions` (`.pre-commit-config.yaml:170-177`) and
  `check-false-pass-patterns` (`:181-188`) are both `repo: local`, `language: script`,
  `types: [python]`, `pass_filenames: false`, `always_run: true`. But
  `check-error-log-assertions` is **`stages: [push]`** (`:177`) and therefore never runs on commit
  and never runs under `pre-commit run --all-files`. Only `check-false-pass-patterns`
  (`stages: [commit]`, `:188`) is a valid structural model, and only for its wiring shape.
- **Stage names in this config are deprecated.** *Checked at `35d5f61`.* `.pre-commit-config.yaml:36`
  sets `default_stages: [commit]`, and hooks use the legacy `commit` / `push` / `manual` names. All
  installed pre-commit versions accept them while printing
  `[WARNING] … uses deprecated stage names … which will be removed in a future version`.
- **`--no-verify` is blocked; `SKIP=` is not.** *Checked at `35d5f61`.* A global
  `block-no-verify.sh` PreToolUse hook denies `git … --no-verify` and `commit -n`. It matches on
  those strings only, so `SKIP=<hook-id> git commit` bypasses any pre-commit hook without tripping
  it, as does running git outside that harness entirely.
- **`page.waitForRequest` has zero uses** in `frontend/tests/` (*checked at `35d5f61`*; grep returns
  matches only under `node_modules/`), so it is a live *future* risk rather than a present gap.

### The precedent this feature is correcting, and who found it

`check-false-pass-patterns` is wired as `entry: ./scripts/check-false-pass-patterns.sh
--staged-only`, `stages: [commit]`. It is not in the CI job's `SKIP` list, so it runs in the
`pre-commit` job. In that job it does nothing.

The script's `--staged-only` branch resolves its file list from
`git diff --cached --name-only --diff-filter=ACM` (`scripts/check-false-pass-patterns.sh:39-41`).
On a CI runner, `actions/checkout` leaves the index matching `HEAD`, so that diff is empty, the
script prints `No test files to check`, and exits 0 (`:47-49`).

**This was not discovered by this feature.** It is documented in the repo already, in the
`pre-commit` job's own `env:` block at `pr-checks.yml:236-240`: *"check-false-pass-patterns uses
--staged-only and thus NO-OPS in CI (nothing is staged) — it gates local commits only; not claimed
as CI coverage here (honesty, per this feature's whole point)."* Feature 1400 found it and chose to
write it down rather than paper over it. 002 inherits the lesson, not the credit.

There is a second axis 1400's note does not call out: the script's file filter is `^tests/.*\.py$`
(`:41`) and its non-staged branch is `find tests/e2e -name "*.py"` (`:44`). Both target the **admin**
pytest suite. It could never have covered `frontend/tests/e2e/*.ts` under any invocation, so its
scope was never this class of defect either.

The operative conclusion for 002 is that a guard can be *present*, *not skipped*, *green*, and
*inert*, and that the failure has more than one axis: invocation mode, scan scope, hook stage,
runtime environment, and whether the job it runs in can block anything. FR-007 verifies against all
of them rather than one.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A reintroduced race is caught before it lands (Priority: P1)

A contributor adds a Playwright test that fills a search box and then awaits
`page.waitForResponse(...)` on the following line. They commit.

**Why this priority**: this is the entire feature. Everything else is supporting structure.

**Independent Test**: plant that exact shape in a scratch file under `frontend/tests/e2e/`, stage
it, and attempt a commit. The commit is refused with a message naming the file, the line, and the
correct promise-first shape.

**Acceptance Scenarios**:

1. **Given** a clean post-001 tree where the guard reports zero racy sites, **When** a contributor
   stages a new test containing an act-then-wait `page.waitForResponse`, **Then** the commit is
   refused and the output names `file:line` and states the required promise-first ordering.
2. **Given** the same violation reaching a pull request without a local hook run, **When** the PR's
   **`Lint`** job runs, **Then** that job fails. Because `Lint` is a required status check, the PR
   cannot be merged, including by `gh pr merge --auto --squash`.
3. **Given** a contributor writes the promise-first shape correctly, **When** they commit, **Then**
   the guard passes and adds no friction.
4. **Given** a contributor writes an act-then-wait `page.waitForEvent('requestfailed')`, **When**
   they commit, **Then** it is refused identically. Coverage is by shape, not by method name.

---

### User Story 2 - The guard is provably not decorative (Priority: P1)

A maintainer six months from now needs to know whether the green check means anything.

**Why this priority**: co-equal P1 with US1. A guard whose effectiveness is unverified is
indistinguishable from no guard, and this repo has a live, self-documented example of exactly that
failure. Shipping US1 without US2 ships a claim, not a control.

**Independent Test**: run the guard in every invocation mode against a planted violation and record
each non-zero exit as evidence.

**Acceptance Scenarios**:

1. **Given** a planted violation in the working tree, **When** the guard runs in the local
   pre-commit invocation, **Then** it exits non-zero.
2. **Given** the same planted violation present, **When** `pre-commit run --all-files` runs on a
   checkout whose index matches `HEAD`, **Then** it exits non-zero. An empty staged diff MUST NOT be
   able to produce a pass.
3. **Given** the same planted violation present, **When** the detector is invoked with
   **site-packages disabled** (`python3 -I -S`), **Then** it exits non-zero. This approximates the
   CI `Lint` job's dependency set, where only ruff is installed.
4. **Given** the same planted violation present on a draft pull request, **When** CI runs, **Then**
   the **`Lint`** required check fails. This is the only scenario that exercises the wiring rather
   than the detector.
5. **Given** the planted violation is reverted, **When** every invocation is repeated, **Then** all
   exit zero.
5. **Given** the detector script is missing, renamed, or unrunnable, **When** any enforcement point
   runs, **Then** it fails loudly rather than passing.

---

### User Story 3 - The classification rule has exactly one home (Priority: P2)

Someone adds a new triggering-action idiom to the suite and needs to teach the detector about it.

**Why this priority**: correctness over time. 001's AR#3 found `.evaluate(` in live use at
`error-visibility-search.spec.ts:158` after an earlier seven-token list had already been called
complete. The token list will need editing again, and it must be editable in one place.

**Independent Test**: grep the executable surface of the repository for the trigger-action token
list. Exactly one definition site exists.

**Acceptance Scenarios**:

1. **Given** the guard is installed, **When** a maintainer greps outside `specs/` for a trigger
   token such as `setInputFiles`, **Then** the only definition-site hit is 001's scan script.
2. **Given** a maintainer adds a token to that list, **When** they re-run the guard, **Then** every
   enforcement point picks up the new token with no second edit anywhere.

---

### User Story 4 - The board reflects the closed loop (Priority: P3)

**Why this priority**: bookkeeping, and it depends on 001's board edits landing first.

**Independent Test**: grep `CLEANUP-BOARD.html` for the named card titles and confirm each exists.

**Acceptance Scenarios**:

1. **Given** 001's board edits have landed, **When** 002 lands, **Then** `CLEANUP-BOARD.html`
   contains a card recording the guard as the closing half of the race-class work, plus one card per
   FR-011 deferred item.

### Edge Cases

- **A contributor legitimately needs a shape the classifier calls `OTHER`.** `OTHER` does not fail
  the gate (only `RACY` does), but it is printed under 001's "requires human triage" banner. The
  guard must not convert that banner into a hard failure, or every novel-but-correct shape becomes
  a blocked commit.
- **A commit touches no test files at all.** With `always_run: true` and a whole-tree scan, the
  guard still runs. That is intended: it means a violation cannot arrive via a merge, a rebase, or a
  revert that stages nothing under `frontend/tests/e2e/`.
- **`SKIP=<hook-id> git commit`.** A known, unclosable local bypass. `block-no-verify.sh` matches
  `--no-verify` and `commit -n` only, so `SKIP=` passes it, as does running git outside that
  harness. This is precisely why FR-004 puts the blocking enforcement point in a **required CI
  job** rather than relying on the local hook. The local hook is a fast-feedback convenience; the
  required job is the control.
- **`SKIP=` set in the workflow.** FR-004's `Lint` step is a plain `run:` step, not a pre-commit
  hook, so the `pre-commit` job's `SKIP` env cannot disable it.
- **The scan script is deleted in the same commit that would introduce a violation.** FR-008 covers
  the detector being absent; every enforcement point must fail rather than pass.
- **`frontend/tests/e2e/` is empty, missing, or renamed.** Covered by FR-013: zero files scanned is
  itself a failure, because "found no violations" and "found no files" are the same exit code
  otherwise, and a directory rename would silently turn the guard green forever.
- **Someone adds Playwright specs outside `frontend/tests/e2e/`.** Out of the detector's root, so
  silently unguarded. Carded under FR-011(c) rather than solved here.
- **A violation is introduced by a machine, not a person** — a codemod or an AI-assisted edit that
  never runs a local hook. The required-job enforcement point is the one that catches this.
- **Fork PRs and path filters.** *Checked at `35d5f61`:* `pr-checks.yml:18-26` declares
  `pull_request: branches: [main]` with **no `paths:` filter**, so the `Lint` job runs on every PR
  to `main` including from forks. No gap here today; a future `paths:` filter would introduce one.
- **The deprecated stage names are removed by a future pre-commit release.** `default_stages:
  [commit]` and `stages: [push]` are already warned as scheduled for removal. FR-003 requires the
  new hook use the modern `pre-commit` stage name so this feature does not add to that debt, and
  FR-011(e) cards the config-wide migration.
- **Six months unattended.** The three failure modes are: the detector is renamed (FR-008), the scan
  root is renamed (FR-013), and the `Lint` job's Python is bumped past what a stdlib-only script
  tolerates (low risk, and the job fails loudly rather than silently if so).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The guard MUST refuse a commit locally, and MUST fail a **required** CI status check,
  when any file under `frontend/tests/e2e/` contains an awaited `page.waitForResponse(...)` or
  `page.waitForEvent('requestfailed'|'response')` whose immediately preceding non-comment,
  non-blank line performs a triggering action. This is the `RACY` classification from 001 FR-011,
  reused verbatim rather than restated.

- **FR-002**: The guard MUST reuse `scripts/scan-waitforresponse-race.py` from 001 as its detector.
  It MUST NOT reimplement the classification rule in a second language or a second file. The
  trigger-action token list, the comment-exclusion rule, the adjacency rule, and the
  `waitForEvent` coverage all have exactly one definition site, and it is that script.

  Rationale, since this is the feature's central decision: a second implementation is a second
  truth. 001's history shows the token list is not stable — it grew from seven tokens to thirteen when
  `.evaluate(` was found live during AR#3 — and a JavaScript copy of an evolving Python list is a
  drift generator. It would reproduce the precise class of miss (a detector whose framing is
  narrower than the defect) that let 3 sites hide.

- **FR-003 (local enforcement point)**: The guard MUST be wired as a `repo: local` hook in
  `.pre-commit-config.yaml` with `pass_filenames: false`, `always_run: true`, and
  `stages: [pre-commit]` stated explicitly.

  Constraints, each closing an observed failure mode:
  - It MUST use `language: system` with an entry of the form
    `python3 scripts/scan-waitforresponse-race.py`. This requires no shebang and no mode change on
    the detector, keeping FR-010's file allowlist honest, and it avoids the `.venv/bin/python3`
    entry form that would fail on a CI runner.
  - It MUST NOT use `stages: [push]` or `stages: [manual]`. `check-error-log-assertions` is
    `stages: [push]` and is therefore **not** a valid template despite looking like one; a push-stage
    hook fires on neither `git commit` nor `pre-commit run --all-files`, which would defeat US1 and
    US2 simultaneously while producing no output to notice.
  - It MUST use the modern `pre-commit` stage name rather than the deprecated `commit` alias, so the
    guard does not depend on a name its own tooling has announced for removal.
  - It MUST NOT be added to the `SKIP` list of the `pre-commit` job in `pr-checks.yml`.

- **FR-004 (blocking enforcement point)**: The guard MUST additionally run as a step in the
  **`Lint`** job of `.github/workflows/pr-checks.yml`, invoking the same detector directly.

  This is the requirement that makes FR-001's "MUST fail CI" true. `Lint` is one of the four
  required status checks on `main` (`["Secrets Scan", "Lint", "Run Tests", "Playwright E2E Tests"]`); the `Pre-commit Hooks`
  job is not, so a guard reaching CI only through the pre-commit config would be advisory and could
  not stop `gh pr merge --auto --squash`. The `Lint` job already provides Python 3.13 via
  `actions/setup-python@v7` and installs only ruff, so the step adds no dependency.

  This does **not** duplicate the detector, only its invocation, so FR-002's single-source-of-truth
  property is preserved. The alternative — adding `Pre-commit Hooks` to the required contexts — is a
  repository settings change requiring admin rights and is deliberately **out of scope**, recorded
  as an owner decision under FR-011(f).

  The step MUST carry `if: always()`. GitHub Actions steps are fail-fast, and the guard is placed
  last in the job (Clarification C4), so without it any of the three preceding ruff steps failing
  means the guard never runs and produces no output at all. A PR that is both ruff-dirty and
  race-dirty would report only the ruff failure, and the contributor would discover the race on a
  second round trip. With `if: always()` the job still fails; both failures surface in one run.

  The step MUST be a plain `run:` step, not a `pre-commit` invocation, so the `pre-commit` job's
  `SKIP` environment variable cannot reach it.

- **FR-005**: The detector MUST be runnable with the standard library alone, under a bare
  `python3` (3.13) interpreter, with no `.venv`, no `pip install`, and no import of anything in
  `requirements-*.txt`.

  This is a **change request against 001 task T001**, whose criterion 8 specifies invocation under
  the project venv. Venv invocation remains valid and is unaffected; this requirement adds that
  venv availability MUST NOT be a precondition, because the `Lint` job has no venv. If 001's
  implementation introduces a third-party import, that is a defect against this requirement and must
  be reconciled before 002 can land.

- **FR-006**: The guard's failure output MUST name each offending `file:line` and MUST include a
  literal corrected example showing the promise-first ordering, so a contributor can act on it
  without opening this spec. Verifiable by asserting the output contains the offending `file:line`
  and a line matching `const <name>Promise = page.waitForResponse` before the triggering action.

- **FR-007**: The guard MUST be verified against a **deliberately planted violation** in all four
  modes before it is accepted:
  (a) the local commit path on a staged violation (`git commit`, not merely `pre-commit run`);
  (b) `pre-commit run --all-files` against a checkout whose index matches `HEAD`;
  (c) a **site-packages-free** invocation, `python3 -I -S scripts/scan-waitforresponse-race.py`;
  (d) a real CI run: a draft pull request carrying the planted violation, on which the **`Lint`**
  required check is observed to fail.
  Each MUST exit non-zero with the violation present and zero with it absent. The planted violation
  MUST NOT be merged, and MUST NOT survive on any branch after verification.

  Mode (c) MUST use `-I -S` and MUST NOT use `env -u VIRTUAL_ENV`. Unsetting `VIRTUAL_ENV` clears a
  marker variable while leaving `.venv/bin` on `PATH`, so `python3` still resolves inside the venv —
  verified in this repo, where `env -u VIRTUAL_ENV bash -c 'command -v python3'` returns
  `.venv/bin/python3`. Scrubbing `PATH` instead selects the system interpreter, which is 3.12 or
  3.10 on a CLAUDE.md-conformant machine and so tests the wrong version. `-I` with `-S` keeps 3.13
  and removes site-packages, which is exactly the FR-005 property.

  Modes (c) and (d) are not redundant with (b). The `check-false-pass-patterns` precedent went inert
  on the *invocation mode* axis; verifying only that axis repeats the spec's own error one level up,
  because (a) and (b) both run where `.venv` is importable and neither can detect a detector with a
  third-party dependency. Mode (d) is the only one that exercises the wiring rather than the
  detector, and it follows 1400 T006's draft red-team PR precedent. Local green on an unmodified
  tree is not evidence at all — the pre-001 tree also went green on `npm run lint` while holding 27
  violations.

- **FR-008**: Every enforcement point MUST fail loudly if the detector is absent, unrunnable, or
  exits non-zero for any reason other than `RACY > 0`. A missing detector, an unresolvable
  interpreter, or an internal exception MUST NOT be reported as a pass. The detector MUST NOT catch
  a scanning exception and exit 0; any such swallow is a defect against this requirement.

- **FR-009**: The guard MUST be introduced only on a tree where 001's sweep has already landed, so
  it is green on arrival. It MUST NOT ship with a suppression list, a baseline file, an allowlist,
  or a non-gating mode. Per 1400 AR3-F2, once green it MUST NOT be softened to decorative; a future
  violation is fixed, not exempted.

- **FR-010**: No product-code changes and no changes to test assertions. This feature adds
  enforcement wiring and verification evidence only. The set of files it may modify is
  `.pre-commit-config.yaml`, `.github/workflows/pr-checks.yml`, `Makefile`, `CLEANUP-BOARD.html`,
  and this spec directory. It MUST NOT edit `scripts/scan-waitforresponse-race.py` except where
  FR-005 or FR-012 reveals a mismatch with 001's delivered implementation, and any such edit MUST be
  recorded as a change against 001's T001 acceptance criteria rather than made silently.

- **FR-011**: Deferred items MUST be recorded as cards in `CLEANUP-BOARD.html` rather than dropped:
  (a) `page.waitForRequest` coverage, currently zero-use and therefore a future risk;
  (b) editor-time feedback via a custom ESLint rule, which today would require changing the
  `next lint` invocation to reach `frontend/tests/`;
  (c) extending the scan root beyond `frontend/tests/e2e/` if Playwright specs are ever added
  elsewhere;
  (d) the `check-false-pass-patterns` CI inertness and its admin-suite-only scope, already
  documented at `pr-checks.yml:236-240` and belonging to that feature to fix;
  (e) migrating `.pre-commit-config.yaml` off deprecated stage names
  (`pre-commit migrate-config`), which affects every hook in the file and so is not this feature's
  to perform;
  (f) the owner decision on whether `Pre-commit Hooks` should be added to `main`'s required status
  checks, completing 1400 FR-007 step (b) for that job;
  (g) `scripts/` is outside every **required** CI check. Verified: the `Lint` job runs
  `ruff format --check --diff src/ tests/`, `ruff check src/ tests/`, and `ruff check src/ --select S`;
  the bandit hook is `-r src/`; `make sast` scans `src/`; `make lint` is `ruff check src tests`. The
  detector is linted only by the `ruff-check` / `ruff-format` pre-commit hooks, which in CI run
  solely in the **non-required** `Pre-commit Hooks` job. This feature promotes a `scripts/` file into
  the required merge path without any required check covering it.

- **FR-015** *(out of numeric order: FR-012, FR-013 and FR-014 follow this entry. FR-015 was added
  during AR#1 and appended next to the FR-010/FR-011 scope block it belongs with. Do not stop
  reading here — FR-012 carries the detector interface contract, AR#3 G-17)*: This feature MUST
  correct the two in-repo statements that the `pre-commit` job is a blocking gate:
  the comment block in `.pre-commit-config.yaml` reading *"runs these hooks on every PR to main as a
  **BLOCKING** gate"* (at `:190-192` today, but locate it by that string — the new hook is inserted
  into the same file first and shifts it, AR#3 G-10) and the step name at `pr-checks.yml:229`
  (*"Run pre-commit (blocking)"*). Both are false
  against `main`'s verified `required_status_checks.contexts`, and both files are already inside
  FR-010's allowlist.

  This is not scope creep, and the distinction matters. `.pre-commit-config.yaml:190-192` is
  **the sentence this feature's own Stage 1 draft read and believed**, producing AR#1's CRITICAL
  finding F-01 and a design that would have shipped an advisory guard. The new hook lands a few
  lines below it. Leaving the claim in place while adding a hook that depends on the opposite fact
  guarantees the next reader repeats the error, and this feature would have fixed its own text while
  leaving the source of the mistake intact. The correction is two comment edits.

- **FR-012 (detector interface contract)**: Because the detector does not exist yet, 002 pins the
  interface it wires against. The detector MUST satisfy:

  | Aspect | Contract |
  |---|---|
  | Invocation | `python3 scripts/scan-waitforresponse-race.py`, no required arguments, runnable from the repo root |
  | Exit 0 | `RACY == 0` **and** at least one file was scanned |
  | Exit 1 | `RACY > 0` |
  | Exit non-zero, non-1 | any internal error; MUST NOT be 0 |
  | Findings output | `file:line CLASSIFICATION` per site, on stdout |
  | Summary output | counts for `RACY` / `PROMISE-FIRST` / `OTHER` **and** the number of files scanned |
  | Triage banner | `OTHER` sites listed under an explicit "requires human triage" heading; does not affect exit code |

  Any divergence between this table and 001's delivered script MUST be reconciled as an amendment to
  001 T001, not absorbed silently into 002's wiring.

- **FR-013**: The detector MUST report the number of files scanned, and a scan that examines **zero**
  files MUST exit non-zero. "No violations found" and "no files found" MUST NOT share an exit code.
  This closes the cheapest route to a permanently green inert guard: renaming or moving
  `frontend/tests/e2e/`. A zero-file scan MUST exit non-zero whether the root is **missing, renamed,
  or present but empty** — testing only the rename passes a detector that raises on a missing
  directory and returns 0 on an empty one (AR#3 G-08). This requirement is now carried by 001 T001
  criteria 5 and 6 directly, folded in at `3b86d9c`. It was originally filed as an amendment against
  criterion 5 (four counts, no files-scanned) and criterion 6 (whose `sys.exit(0)` "otherwise"
  branch returned 0 on an empty scan); both criteria have since been rewritten.

- **FR-014**: The guard MUST be exposed through a `make` target, that target MUST
  shell out to the same detector rather than duplicating any logic, and MUST be added to the
  `validate` target's dependency list, consistent with how `check-test-target-headers` is wired at
  `Makefile:42`.

### Key Entities

- **Detector**: `scripts/scan-waitforresponse-race.py`, owned by 001, contracted by FR-012.
  Classifies every call site as `RACY` / `PROMISE-FIRST` / `OTHER`. 002 consumes it, does not own it,
  and files amendments rather than edits.
- **Local gate**: a `repo: local` pre-commit hook (FR-003). Fast feedback. Bypassable via `SKIP=`.
- **Blocking gate**: a step in the required `Lint` job (FR-004). Not bypassable by a contributor.
- **Planted violation**: a temporary act-then-wait site used solely as FR-007 evidence. Never
  committed.

## Success Criteria *(mandatory)*

Each criterion names the command that decides it.

- **SC-001**: On the post-001 tree with the guard installed, `pre-commit run --all-files` exits 0,
  and the detector reports `RACY 0 / PROMISE-FIRST 16 / OTHER 1`, total **17**, across **48** files
  scanned. The 16/17 figures are 001's (SC-001, T018 criterion 1), not this feature's, and MUST NOT
  be adjusted to match whatever the detector happens to print — that would discard the only
  independent check that it counted the right things.
- **SC-002**: With a planted violation staged, `git commit -S` is **refused** (non-zero, no commit
  object created) and the output contains the planted `file:line`. Asserted with `git commit`, not
  `pre-commit run`, because the commit path is what US1 promises.
- **SC-003**: With the same planted violation present but **unstaged**, `pre-commit run --all-files`
  on a checkout whose index matches `HEAD` exits non-zero. This is the assertion that distinguishes
  this guard from `check-false-pass-patterns`.
- **SC-004**: With the same planted violation present,
  `python3 -I -S scripts/scan-waitforresponse-race.py` exits non-zero. `-I -S` is required; see
  FR-007 mode (c) for why `env -u VIRTUAL_ENV` does not test what it appears to.
- **SC-005**: On the post-001 tree **without** a planted violation,
  `python3 -I -S scripts/scan-waitforresponse-race.py` exits **0**. This is the durable FR-005
  check: it fails the moment anyone adds a third-party import to the detector, rather than relying
  on a one-time Phase A inspection.
- **SC-006**: A draft pull request carrying the planted violation shows the **`Lint`** required
  check as failed (`gh pr checks`). This is the only criterion that exercises the wiring rather than
  the detector.
- **SC-007**: `grep -rn "scan-waitforresponse-race" .pre-commit-config.yaml .github/` returns hits in
  **both** `.pre-commit-config.yaml` and `.github/workflows/pr-checks.yml`, inverting 001's T001
  criterion 9.
- **SC-008**: `! grep -A3 'SKIP:' .github/workflows/pr-checks.yml | grep -q scan-waitforresponse-race`
  succeeds — written as a negated `grep -q`, not `grep -c ... = 0`, because `grep -c` exits 1 on a
  zero count and the success case would report as a failure (AR#3 G-19) — and the guard's step under
  `jobs.lint.steps` has a `run:` key (not a `uses:` or a
  `pre-commit` invocation), so the `pre-commit` job's `SKIP` cannot reach it.
- **SC-009**:
  `grep -rn "setInputFiles" --include='*.py' --include='*.js' --include='*.ts' --include='*.yaml' . | grep -v node_modules | grep -v '^./specs/' | cut -d: -f1 | sort -u | wc -l`
  returns **1**, and that file is `scripts/scan-waitforresponse-race.py`.

  Two things about this command are deliberate. It counts **files, not lines**: any real
  implementation holds the thirteen tokens both in the module docstring (001 T001 criterion 3
  requires them verbatim there) and in an executable list, so a line count returns ≥2 on a correct
  build and the criterion would read as a false failure — the same trap 001 hit with its own
  `searchAndAwaitResponse` grep. And the `specs/` exclusion is needed because `specs/` contains real
  `.ts` and `.yaml` files that the `--include` filters match. It is *not* needed for
  `001/tasks.md:61-63`, which is Markdown and unreachable by these filters; an earlier draft gave
  that as the reason, which would have led the next reader to delete the exclusion as unnecessary.
- **SC-010**: The detector's wall-clock runtime on the full scan root (**48** `.ts` files
  post-001, of which 6 contain matches) is measured with `time` and recorded, and is **under 2
  seconds**. A measured figure is required; an estimate does not satisfy this.
- **SC-011**: With `frontend/tests/e2e/` temporarily renamed, the detector exits non-zero rather
  than reporting a clean scan.
- **SC-012**: With `scripts/scan-waitforresponse-race.py` temporarily renamed, **both** the
  pre-commit hook and the `Lint` job's command shape exit non-zero. This is FR-008's only
  verification; without it, "a missing detector must not read as a pass" is asserted by construction
  and checked by nobody.
- **SC-013**: `make validate` exits non-zero with a planted violation present, and
  `grep -n 'check-waitforresponse-race' Makefile` shows the target on the `validate` dependency
  line.
- **SC-014**: All required cards exist in `CLEANUP-BOARD.html`, verified by counting cards whose
  `source` field is `002-waitforresponse-lint-guard`: exactly **8** — one guard card plus one per
  FR-011 item (a) through (g), which is seven items. Total board count goes 118 → 120 (after 001's
  two follow-up cards) → **128**. Counting by `source` rather than "locatable by grep" is
  deliberate: an unspecified grep pattern is satisfied by any eight cards, or by none.
- **SC-015**: No file outside the FR-010 allowlist is modified, verified by `git diff --stat` against
  the branch point; and, after Phase E completes, the planted violation exists in no commit on
  `main` and on no surviving branch or open PR. It necessarily exists on the temporary
  `tmp/gate-red-team` branch while FR-007 mode (d) runs, which is what that mode tests. The earlier
  absolute wording ("no commit on any branch") contradicted mode (d) and was unsatisfiable alongside
  it (AR#3 G-11). FR-007's phrasing is the one of record.

## Out of Scope

- Fixing the 27 existing racy sites. That is 001.
- Adopting `eslint-plugin-playwright` wholesale. It has no rule for this pattern and would flag
  unrelated violations suite-wide; 001's spec already places it out of scope.
- Writing a custom ESLint rule now. Deferred under FR-011(b) because `next lint` does not reach
  `frontend/tests/`, so the rule would not execute.
- Changing what any test asserts, or any product code.
- Making the Playwright E2E job a required merge check. The owner explicitly deferred that decision
  to after the sweep lands and the job shows a clean streak.
- Adding `Pre-commit Hooks` to `main`'s required status checks. This is a repository settings change
  needing admin rights and it would retroactively make every currently-non-blocking hook blocking, a
  much larger blast radius than this feature. Carded under FR-011(f) as an owner decision.
- Remediating the `check-false-pass-patterns` CI inertness or its admin-suite-only scope. Carded
  under FR-011(d).
- Migrating the whole config off deprecated stage names. Carded under FR-011(e).
- Extending the detector to `page.waitForRequest`. Zero current uses; carded under FR-011(a).

## Assumptions

- 001 lands before 002. Every requirement here assumes `scripts/scan-waitforresponse-race.py` exists,
  satisfies FR-012, and reports `RACY 0` on the tree 002 is applied to.
- `Lint` remains a required status check on `main`. If it is removed from
  `required_status_checks.contexts`, FR-004's blocking property is lost and the enforcement point
  must move. This is the single external condition the feature's correctness depends on.
- **pre-commit version skew is accepted, with evidence.** Three pins exist:
  `requirements-dev.txt:37` and `requirements-ci.txt:58` pin `4.6.1`, `pr-checks.yml:218` pins
  `4.6.0`, and the project `.venv` currently runs `4.5.1`. Stage-selection behaviour was confirmed
  identical across all three during AR#1: a stage-less hook under `default_stages: [commit]` runs
  under `pre-commit run --all-files`, a `stages: [push]` hook does not, and all three emit the
  deprecation warning without erroring. FR-003's explicit `stages: [pre-commit]` is valid on all
  three. Reconciling the pins is not this feature's work.
- FR-004 places the blocking check in `Lint`, a job whose name describes linting. A reader may find a
  Playwright race scan there surprising. Accepted deliberately: correctness of the gate outranks
  tidiness of job naming, and the alternative requires an owner-gated settings change. The step MUST
  carry a comment explaining why it lives there.

---

## Adversarial Review #1

Conducted by an independent reviewer against the Stage 1 draft, then re-verified by the
orchestrator. The reviewer was instructed to check every factual claim and line-number citation in
Context against the live tree rather than assess plausibility. It returned 3 CRITICAL, 5 HIGH,
6 MEDIUM, 3 LOW.

**Orchestrator re-verification.** Per the project's refuter standard the reviewer's highest-impact
claims were re-checked directly rather than accepted from its summary. All four load-bearing claims
verified TRUE:

| Re-checked claim | Command | Result |
|---|---|---|
| `Pre-commit Hooks` is not a required status check | `gh api repos/traylorre/sentiment-analyzer-gsk/branches/main/protection --jq '.required_status_checks.contexts'` | `["Secrets Scan","Lint","Run Tests","Playwright E2E Tests"]`; rulesets count `0` |
| The false-pass CI no-op was already documented | `sed -n '230,245p' .github/workflows/pr-checks.yml` | Documented verbatim at `:236-240` |
| `check-error-log-assertions` is `stages: [push]` | `sed -n '168,189p' .pre-commit-config.yaml` | Confirmed at `:177` |
| Scan root holds 47 `.ts` files, not "roughly ten" | `find frontend/tests/e2e -name "*.ts" \| wc -l` | `47` |

Two further checks were run to validate the *resolutions* rather than the findings: the `Lint` job's
environment (`pr-checks.yml:35-65` — `setup-python@v7`, `PYTHON_VERSION: '3.13'`, installs only
ruff) and SC-007's grep, which returns empty on the pre-001 tree as expected and must return exactly
one hit once the detector lands.

### Findings

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| F-01 | CRITICAL | "The CI pre-commit job is a blocking gate" is **false**. `Pre-commit Hooks` is not in `main`'s required contexts, so US1 AS2's "the PR is blocked" was false on day one and the whole CI enforcement point was advisory. 1400 FR-007 step (b) was never performed for that job. | Design changed. New **FR-004** puts the blocking check in the **`Lint`** job, which *is* required, needs no repo-settings change, and already has Python 3.13. Every "blocking gate" claim in Context rewritten to the verified branch-protection state. Adding `Pre-commit Hooks` to required contexts moved to Out of Scope and carded as an owner decision, FR-011(f). |
| F-02 | CRITICAL | The CI `pre-commit` job installs no `.venv` and no project deps. The repo's only Python-hook precedent uses `entry: bash -c '.venv/bin/python3 …'`; copying it would put the guard permanently red in CI, which under F-01 nobody is blocked by, so it would get SKIP-listed. | New **FR-005** requires the detector be stdlib-only and runnable under a bare `python3`, filed as an explicit change request against 001 T001 criterion 8. **FR-003** mandates `language: system` with a `python3 …` entry, never `.venv/bin/python3`. |
| F-03 | CRITICAL | FR-006(b) claimed `pre-commit run --all-files` on a clean index "reproduces the CI condition". It reproduces the *index state* only, not the *environment*. Both original verification modes run where a `.venv` exists, so neither could detect an environment-dependent guard. The spec applied its own lesson to one axis and stopped. | **FR-007** now requires three modes, adding (c): a clean environment with no `.venv` and no project dependencies. New **SC-004** asserts it. The rationale is stated in-line so the third mode is not later pruned as redundant. |
| F-04 | HIGH | FR-003 named `check-error-log-assertions` as a structural template. It is `stages: [push]`, so copying it yields a hook that fires on neither `git commit` nor `pre-commit run --all-files` — defeating US1 and US2 at once, silently. | Removed from the template. FR-003 now cites only `check-false-pass-patterns` for wiring shape and **explicitly forbids** `stages: [push]` and `stages: [manual]`. Context now flags the trap by name. |
| F-05 | HIGH | `SKIP=<hook-id> git commit` bypasses any pre-commit hook. The global block-no-verify guard matches only the bypass flag and `commit -n`. With F-01 unfixed, neither enforcement leg held. | Added as an Edge Case naming the bypass. The resolution is structural: FR-004's required-job step is not a pre-commit hook and is unaffected by `SKIP`. The local hook is now described as fast feedback, the required job as the control. |
| F-06 | HIGH | Three different `pre-commit` pins exist (`4.6.1` in both requirements files, `4.6.0` in the workflow, `4.5.1` in `.venv`); the spec named one. | Assumptions now name all three and record the reviewer's empirical result that stage-selection behaviour is identical across all of them. Reconciling the pins is explicitly not this feature's work. |
| F-07 | HIGH | `default_stages: [commit]` and `stages: [push]` are deprecated with removal announced; building the guard's activation on a legacy alias is a time bomb. | **FR-003** requires the new hook state `stages: [pre-commit]` explicitly. Config-wide migration carded as FR-011(e) rather than performed here, since it touches every hook in the file. |
| F-08 | HIGH | FR-010's allowlist forbade the file changes FR-003's `language: script` shape would require (shebang, `chmod +x`, or a wrapper), and 001 T001 has no criterion making the detector executable. | Resolved by choosing `language: system` with `entry: python3 scripts/...`, which needs no shebang, no mode change, and no wrapper. `.github/workflows/pr-checks.yml` added to the FR-010 allowlist for FR-004. |
| F-09 | MEDIUM | Context claimed "Checked against the working tree, not recalled" while carrying at least three unchecked items, including the eslint-plugin rule count and the "blocking gate" claim — the same epistemic failure the spec diagnoses in the 27 sites. | Every Context bullet now names its evidence source and distinguishes *checked at `35d5f61`* from *carried from 001 research*. The claim that this feature discovered the false-pass inertness is **withdrawn**: it is documented at `pr-checks.yml:236-240` and the credit is now attributed to Feature 1400 in the spec text. |
| F-10 | MEDIUM | "the scan reads roughly ten files" was wrong by ~5x (47 `.ts` files) and contradicted SC-007's demand for measurement. | Estimate deleted. **SC-008** now carries the verified count (47 files, 6 with matches), requires a measured figure, and sets a 2-second budget so the criterion can fail. |
| F-11 | MEDIUM | FR-005/FR-008/SC-006/SC-007 were unfalsifiable as written, and SC-006's literal grep would have failed against `001/tasks.md:61-63`, which enumerates all thirteen tokens. | **FR-006** now names the exact strings the output must contain. **FR-008** adds "exits non-zero for any reason other than `RACY > 0`" and forbids swallowing exceptions. **SC-007** carries the exact command including a `specs/` exclusion, with the exclusion justified in-line rather than left as a dodge. **SC-008** gets a threshold. |
| F-12 | MEDIUM | The detector does not exist — every 001 task is unchecked — yet FR-002 mandated reuse of a file with no signature, no exit-code table, and no defined output stream. | New **FR-012** pins the interface as an explicit contract table (invocation, four exit-code cases, findings output, summary output, triage banner) and requires any divergence be reconciled as an amendment to 001 T001. Context now states plainly that the detector does not exist yet. |
| F-13 | MEDIUM | The "scan root empty or missing" edge case had no FR or SC. A directory rename would silently turn the guard green forever — the cheapest possible route to inertness. | New **FR-013**: the detector must report files-scanned and exit non-zero on a zero-file scan. New **SC-009** renames the directory and asserts the failure. |
| F-14 | MEDIUM | US4 and FR-011 had no success criterion, and US4's precondition ("001's board edits have landed") was untestable from inside 002. | New **SC-010** requires one greppable card for the guard plus one per FR-011 item (a)–(f). US4's Independent Test is now a grep. |
| F-15 | LOW | `frontend/.eslintrc.json` is 3 lines, not 2 — in the paragraph claiming verification. | Reworded to "a single `extends` line and nothing else". |
| F-16 | LOW | The `check-false-pass-patterns` post-mortem was incomplete: beyond the empty staged diff, its filter is `^tests/.*\.py$` targeting the **admin** pytest suite, so it could never have covered `frontend/tests/e2e/*.ts` under any invocation. | Added to Context as a second axis, and the operative conclusion generalised: a guard can go inert via invocation mode, scan scope, hook stage, runtime environment, or a job that cannot block. FR-007 verifies against all of them. |
| F-17 | LOW | `make validate` was never named as an enforcement point despite `Makefile` being in the allowlist and `check-test-target-headers` being the cited precedent for guarding this directory. | **FR-014** now requires that if a make target is added it be wired into `validate`, matching `Makefile:42`. |

Two claims in the Stage 1 draft were outright false and load-bearing (F-01, and the credit claim
corrected under F-09); two were false but cosmetic (F-15, F-10). The reviewer confirmed the 001
T001 dependency table, the C4 citation, the Next.js `ESLINT_DEFAULT_DIRS` chain, and the
`check-false-pass-patterns:39-41 / 47-49` post-mortem as accurate.

### Self-defeat check

The reviewer's central question was whether this feature could ship, report green, and be inert —
reproducing the defect it exists to correct. It found three routes, one of which required no
implementation error at all:

1. **Live on day one (F-01).** The specified CI enforcement point could not block a merge. Ship as
   drafted and a red guard is merged over by `gh pr merge --auto --squash`. Closed by FR-004 moving
   the blocking check into the required `Lint` job.
2. **One-word implementation error (F-04).** Copying the `stages: [push]` template produces a hook
   that runs nowhere and prints nothing, which reads as a pass. Closed by forbidding the stage and
   naming the trap.
3. **Opposite polarity (F-02).** Copying the `.venv/bin/python3` entry form produces a hook that is
   red in CI forever, creating pressure to SKIP-list it. Closed by FR-005 and FR-003's entry form.

The residual risk is now concentrated in one external condition rather than in the design: **the
`Lint` job must remain a required status check.** That is recorded as an explicit Assumption rather
than buried, because it is the single thing whose change would silently make this guard advisory
again.

### Gate

All CRITICAL and HIGH findings resolved in-spec, with the resolutions verified against the live tree
rather than asserted. The feature's design changed materially at this gate: the blocking enforcement
point moved from the `Pre-commit Hooks` job to the required `Lint` job, and the detector acquired a
stdlib-only constraint plus an explicit interface contract.

**0 CRITICAL, 0 HIGH remaining.**

---

## Clarifications

Five ambiguities were identified at Stage 4. **All five were answerable from the codebase or from
existing artifacts; none required owner input.** Each answer records the evidence that supports it
so a reader can overturn it by checking the same source rather than by re-litigating the judgment.

### C1 — Should a `make` target be added, and how should it be wired?

**Answer**: yes. Add `check-waitforresponse-race` and add it to the `validate` target's dependency
list.

**Evidence**: `Makefile:42` reads
`validate: fmt lint security sast check-banned-terms check-test-target-headers`.
`check-test-target-headers` is the existing precedent for a repo-level guard over
`frontend/tests/e2e/*.spec.ts`, and it is wired as a `validate` dependency rather than left
free-floating. Following that shape costs one line and keeps `make validate` an honest name.

A target that exists but is not in `validate` would be a fourth invocation nobody runs, which is the
decorative outcome this feature is built to avoid. Spec FR-014 requires the target shell out to the
detector rather than duplicate logic, so the single-definition property (FR-002) is unaffected.

### C2 — What lane, severity, and source should 002's board cards carry?

**Answer**: the guard card lands in `done` at severity `medium`. The seven FR-011 deferred cards,
(a) through (g), land in `track` at severity `low`, except FR-011(d) and FR-011(f), which are
`medium`.

**Evidence**: `CLEANUP-BOARD.html` currently holds **118** cards
(`raw_decode` on the text following `const CARDS = `). Its vocabularies are:

| Field | Observed values |
|---|---|
| `lane` | `track` (53), `done` (29), `fix` (18), `nice` (13), `probe` (5) |
| `severity` | `low` (42), `medium` (41), `high` (19), `info` (10), `critical` (6) |
| card keys | `title`, `lane`, `severity`, `evidence`, `citation`, `next_action`, `source` — plus an optional eighth, `milestone`, present on 3 of the 118 |

`source` is free text and existing features use their own spec directory name, e.g.
`001-lambda-log-visibility cards.md` (6 cards). 002 follows that convention with
`002-waitforresponse-lint-guard`, which is what makes SC-014 countable.

Severity reasoning: the guard itself is `medium` because it prevents a recurring CI-signal defect
rather than a user-facing or security one. FR-011(d) is `medium` because it records a *live* inert
guard in the repository. FR-011(f) is `medium` because it is an unresolved owner decision about
merge-gate authority. The rest are genuine `low` future-risk items.

Card count arithmetic: 118 today, **120** after 001's two follow-up cards, **128** after 002's
**eight** (one guard card plus seven FR-011 cards, (a) through (g)). This figure moved during AR#2:
FR-011 grew a seventh item when the `scripts/`-outside-required-checks gap was found, and the count
was originally written as seven cards / 127.

### C3 — What should the pre-commit hook id be?

**Answer**: `scan-waitforresponse-race`, matching the detector's filename stem.

**Evidence**: every local hook in `.pre-commit-config.yaml` uses an id identical to its script stem:
`check-error-log-assertions` → `scripts/check-error-log-assertions.sh`,
`check-false-pass-patterns` → `scripts/check-false-pass-patterns.sh`,
`check-branch-collision` → `scripts/check-branch-collision.sh`. Following the convention makes
SC-007's grep (`grep -rn "scan-waitforresponse-race" .pre-commit-config.yaml .github/`) match the
hook id, the entry, and the workflow step with one pattern, which is why the success criterion was
written that way.

Note the deliberate departure from the `check-` prefix: the detector is named `scan-` by 001 and the
id follows the file, not the prefix convention. Renaming the script to `check-` would be an edit to
a file this feature does not own (FR-010).

### C4 — Where in the `Lint` job should the step go?

**Answer**: last, after the three existing ruff steps, carrying an explanatory comment.

**Evidence**: the `Lint` job (`pr-checks.yml:35-65`) runs checkout → setup-python → install ruff →
`ruff format --check` → `ruff check src/ tests/` → `ruff check src/ --select S`. Its identity is
Python linting. A Playwright race scan is a genuine outlier there, placed in that job solely because
it is one of the four required status checks
(`["Secrets Scan", "Lint", "Run Tests", "Playwright E2E Tests"]`), which the `Pre-commit Hooks` job is not.

Placing it last preserves the job's readable narrative and means a ruff failure — the far more
common case — still surfaces first. The comment is not optional: a future maintainer tidying the
`Lint` job would otherwise reasonably move this step out and silently convert the guard back to
advisory. Plan assumption 3 and design decision D2 both record this.

The step must be a plain `run:` step, not a pre-commit invocation, so the `pre-commit` job's `SKIP`
environment variable cannot reach it (SC-008).

### C5 — What happens if 001's delivered detector diverges from `contracts/detector-cli.md`?

**Answer**: 002 blocks at Phase A and files an amendment against 001 T001. It does not adapt its
wiring to fit, and it does not edit the script.

**Evidence**: spec FR-010 confines 002's edits to four files and permits touching
`scripts/scan-waitforresponse-race.py` only via a recorded change request. Two amendments are
**already** filed by this feature and are known divergences from 001's current task text, not
hypotheticals:

| Amendment | Against | Reason |
|---|---|---|
| Detector must be stdlib-only and runnable under bare `python3`; venv must not be a precondition | 001 T001 criterion 8, which specifies venv invocation | The CI `Lint` job has no `.venv` (`pr-checks.yml:35-65` installs only ruff) |
| Detector must report files-scanned and exit non-zero on a zero-file scan | 001 T001 criteria 5 and 6, which specify three counts and a `0`/`1` split only | A renamed scan root would otherwise exit 0 forever (AR#1 F-13) |

The reason this is a real risk rather than a formality: **the detector does not exist yet.** Every
task in `001/tasks.md` is unchecked. 002 is wiring against prose. Plan risk R1 rates this **High**
likelihood and identifies it as a sequencing cost accepted deliberately so that both features can be
reviewed together before either is built.

Adapting the wiring to whatever 001 happens to produce is the failure mode being guarded against
here: it would let a detector that exits 0 on an empty scan, or one that needs a venv, pass through
unremarked and land a guard that is green in CI for the wrong reason.

### Deferred to the Phase 2 summary

**None from this stage.** All five questions were resolved from repository evidence.

One pre-existing item is carried forward for owner visibility rather than as a clarification:
FR-011(f), whether `Pre-commit Hooks` should be added to `main`'s required status checks. That is a
repository settings change requiring admin rights, it is explicitly Out of Scope for this feature,
and it is the unfinished step (b) of 1400 FR-007. It is carded, not blocking.
