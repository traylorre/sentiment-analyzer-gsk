# Evidence Log: CodeQL Coverage Expansion

**Feature**: `001-codeql-coverage` | **Branch**: `001-codeql-coverage`
**Dates in ISO 8601 (`YYYY-MM-DD`), per constitution Amendment 1.5.**

Four records, matching `quickstart.md`'s four skeletons.

---

## EXECUTION STATE, read this first

**This feature is PART-EXECUTED. Pushing is owner-gated and was not authorised in the session that
produced this log (2026-07-31), so `001-codeql-coverage` DOES NOT EXIST on `origin`.**

Measured, not assumed:

```
git ls-remote --exit-code --heads origin 001-codeql-coverage; echo "ls-remote rc=$?"
ls-remote rc=2
```

`gh workflow run --ref` resolves the ref **server-side**, so every dispatch on this branch fails
for a reason that has nothing to do with dispatch permission. T002 exists to catch exactly that
before A1 records the wrong finding, and it fired. Consequently:

- Phase D (merge), Phase E (baseline, "after merge only") and Phase F (close-out) did not run.
- Every dispatch-dependent verification in Phases A, B and C did not run.
- **No unrun check is recorded below as a result.** Where a field is NOT RUNNABLE it names the
  blocking dependency. Nothing here is inferred from "what CI would have said".

What DID run: Phase 0 in full, the read-only half of Phase A, all of Phase B except the optional
control arm, all of Phase C's configuration edits and every local check on them, the read-only
halves of T030 / T032 / T038, and T041 minus its volume-dependent fields.

---

## Probe record

- **Dispatch available (A1): NOT ESTABLISHED, and deliberately NOT recorded as `no`.**
  T007's own routing says a missing remote ref and an absent dispatch permission produce the same
  failure and must not be recorded as the same finding. The ref does not exist, so the permission
  question was never put to the server. No dispatch was attempted; no CI state was changed.

  A READ-ONLY probe of the inputs a dispatch would need, taken 2026-07-31, all of which are
  favourable and none of which is a substitute for the dispatch itself:

  ```
  X-Oauth-Scopes: gist, read:org, repo, workflow
  repos/traylorre/sentiment-analyzer-gsk -> {"permissions":{"admin":true,"maintain":true,
    "pull":true,"push":true,"triage":true},"private":false}
  actions/workflows/pr-checks.yml -> {"id":212094770,"name":"PR Checks","state":"active",
    "path":".github/workflows/pr-checks.yml"}
  .github/workflows/pr-checks.yml:19 -> workflow_dispatch:
  ```

  The workflow is active and declares `workflow_dispatch`, the token carries `workflow` scope, and
  the repository grants `admin` and `push`. **That is evidence the dispatch would probably succeed.
  It is not evidence that it did.** A1 is UNRUN.

### B1 evidence (Q4, no mutation). This section alone satisfies SC-009 and SC-010.

**RUN in full, 2026-07-31. This is the load-bearing half of Phase B and it needed no dispatch.**

- **Source**: run `30581930915`, job `91004036909`, `refs/heads/main`, full-tree Python analysis.
  Log fetched with `gh run view ... --log --job`, `rc=0`, **2,125 lines / 287,655 bytes**, which
  matches Adversarial Review #2's independent measurement exactly. The T011 guard is what makes
  every zero below meaningful: several checks here have ZERO as their PASS value, so a degraded
  fetch would have rendered as a clean pass.

- **Extractor invocation (log line 1480), verbatim**:

  ```
  1480:Analyze (python)	UNKNOWN STEP	2026-07-30T21:05:26.6545649Z [2026-07-30 21:05:26] [build-stdout] Calling python3 -S /opt/hostedtoolcache/CodeQL/2.26.2/x64/codeql/python/tools/python_tracer.py --verbosity 3 -z all -c /home/runner/work/_temp/codeql_databases/python/working/trap_cache -R /home/runner/work/sentiment-analyzer-gsk/sentiment-analyzer-gsk --filter exclude:tests/**/*
  ```

- **`Extracted file` lines total: 152 | under `/tests/`: 0, with `first-grep rc=0`.**
  Both values checked, because the count alone is not a check: a `0` count with `first-grep rc=1`
  would mean the FIRST grep matched nothing, that is, the log is wrong or empty, NOT that no test
  file was extracted.

- **Coverage summary (log line 2067), verbatim**:

  ```
  2067:Analyze (python)	UNKNOWN STEP	2026-07-30T21:06:03.6744586Z CodeQL scanned 152 out of 154 Python files and 5 out of 5 GitHub Actions files in this invocation.
  ```

- **Tracked `.py` files: 544 total, 393 under `tests/`, none of them in the database.**
  Both numbers re-measured at this commit and both are as the runbook states.

- **Conclusion**: `paths-ignore` performs the exclusion at **EXTRACTION** time. The `tests/**`
  query filter is **INERT**. The line-13 comment was **FALSE** and has been removed (T017).
  Of F3's three claims, exactly the first is true. **Arms 1 and 2 are ANSWERED (FR-009b) and were
  not run.**

- Note the 152-vs-154 residual and the 5 GitHub Actions files: the Python leg also analyzes
  workflow YAML. That is why the E2 partition at T034 carries an `other` bucket, and why a
  two-bucket `js/` plus `py/` split would silently drop `actions/`-prefixed alerts.

### B2 control arm (OPTIONAL, the only permitted mutation)

- **Status: `NOT RUNNABLE (FR-009c)`**
- **Blocking dependency**: the arm requires `git push origin "$BR"` followed by
  `gh workflow run --ref "$BR"`. Pushing is owner-gated and was not authorised, and the ref does
  not exist on `origin` (`ls-remote rc=2`).

| Arm | Config as run (verbatim) | Analysis id | Commit sha | Results under tests/ | Rule ids | Paths |
|---|---|---|---|---|---|---|
| 3 control | NOT RUN | n/a | n/a | n/a | n/a | n/a |

- Does `py/incomplete-url-substring-sanitization` still fire on current Python test code?
  **UNKNOWN. Not measured, and not guessed.** F4 records that six of the eight historical alerts
  for this rule are `fixed`, which is consistent with the rule no longer firing and consistent with
  it firing; it distinguishes nothing.
- **Filter decision: RETAIN unchanged.** This is FR-009b's stated default and it governs identically
  for `NOT RUN` and `NOT RUNNABLE`. Deleting a rule without evidence is precisely what FR-008
  forbids. **Neither outcome fails SC-009 or SC-010**, which B1 above already satisfies.
- **FR-011 resolution applied (T017)**: `.github/codeql/codeql-config.yml` rewritten so its comments
  and its rules agree. The false claim at the old line 13 ("All other security rules apply to
  tests") is **deleted, not annotated**, as are the two passages carrying the same false
  implication: the old developer-facing bullet describing the exclusion as scoped to the URL
  sanitization rule, and the old line 22 ("But we still want to scan tests for other issues, so we
  use query filters instead"). The extraction-time behaviour is now stated explicitly with its
  evidence cited inline. No rule was added or deleted. Verified:
  `grep -n 'All other security rules apply to tests' -> rc=1`;
  `grep -c 'paths-ignore' -> 1`; `grep -c 'py/incomplete-url-substring-sanitization' -> 1`;
  `git log --oneline origin/main..HEAD -- .github/codeql/codeql-config.yml` shows no `control arm`
  commit, because no arm ran.

### FR-006 record (T013): shared config rules reviewed against the new leg

```
grep -cE '^(paths-ignore|query-filters|paths|queries|disable-default-queries|packs):' \
  .github/codeql/codeql-config.yml
2
grep -nE '^[a-z-]+:' .github/codeql/codeql-config.yml
15:name: "sentiment-analyzer-codeql-config"
19:paths-ignore:
23:query-filters:
```

Exactly **two** rule blocks and exactly **three** top-level keys, so no rule block exists that this
review has not covered. Both rules, with a disposition each:

| Rule | Applies to the new leg? | Disposition |
|---|---|---|
| `query-filters` naming `py/incomplete-url-substring-sanitization` | **No.** A Python rule identifier cannot match any JavaScript or TypeScript rule. | **INERT for the new leg.** Retained (see B2 above). |
| `paths-ignore: tests/**/*` | **Yes.** Genuinely language-neutral. | **DOES apply.** Being root-anchored it reaches `tests/load/api-load-test.js` and does NOT reach `frontend/tests`. |

### FR-007 / FR-007a (T014), TRANSCRIBED from Clarification Q4, not re-derived

- **FR-007 decision**: `frontend/tests` is **IN SCOPE** for scanning. 101 files, about 19,900 lines.
- **FR-007a asymmetry, argued**: the asymmetry is larger than glob anchoring alone suggests. The
  Python side is an extraction-level exclusion removing 393 files from the database entirely. The
  `frontend/tests` side is 101 files matching no exclusion pattern at all. Narrowing or widening
  either side requires editing a rule in the shared config, which **FR-008** bars until the
  surviving control question is answered. The asymmetry is therefore **preserved deliberately for
  this feature's duration, because resolving it would require exactly the unprobed rule change
  FR-008 exists to prevent.** The symmetry question stays carded, already in Out of Scope, with no
  tech debt registry entry per the Q2 triage, and is carried to the named decider at
  `enforcement-recommendation.md` item 6a.

### Deferrals

- **Deferral 2 (10-working-day triage window, Q5)**: raised at Phase A as required. The owner was
  not available in the session that produced this log, so the fallback both T009 and T036 specify
  applies. The literal string is written into the baseline record below:
  `WINDOW: 10 working days, ASSUMED, Deferral 2 unanswered at capture`.
  **Consequence, recorded rather than glossed**: if the owner later names a different number, that
  change is the FR-016a extension and spends the single permitted extension on an authoring
  correction instead of on alert volume. That is the cost T009 exists to avoid, and it has been
  incurred.
- **Deferral 1 (stale constitution §9 registry path, Q2)**:
  `DEFERRAL 1: routed to enforcement-recommendation.md (F2), not blocking`.
  Carried **verbatim** at `enforcement-recommendation.md` item 8, inheriting that document's named
  decider and decision-by date. Question as carried: constitution §9 cites
  `docs/TECH_DEBT_REGISTRY.md` at `.specify/memory/constitution.md` lines 527, 569 and 584, but the
  registry has lived at `docs/reference/TECH_DEBT_REGISTRY.md` since `f8db8d2` (PR #668). Amend §9
  to the real path, or move the file back?

### FR-004, FR-004a, FR-004b decisions (T021)

Scoped measurement, taken over the `codeql` job block only:

```
codeql job = lines 291 to 326
sed -n "291,326p" .github/workflows/pr-checks.yml | grep -c 'npm install\|npm ci\|yarn install\|pnpm install'
0
```

The **unscoped** form of that grep prints `2`, at lines 433 and 520, and both hits are
`cd frontend && npm ci` in the frontend-test and Playwright jobs. Neither is the analysis job and
neither is what FR-004a speaks to. The scoped form is the check.

- **FR-004 (build)**: **NO build step.** `autobuild` stays unconditional and is a no-op for
  JavaScript and TypeScript. If a first run contradicts that, the prerequisite is to be stated
  explicitly and provisioned, not worked around.
- **FR-004a (dependency install)**: **NO install**, both reasons recorded. First, the analysis job
  holds `security-events: write` and is triggered by `pull_request` on a **public** repository, so
  an install step there would execute contributor-authored package lifecycle scripts inside a job
  holding write access to the security-events surface; fork runs get a downgraded read-only token,
  branch pushes by any account with write access do not. Second, the feature is scoped to
  first-party findings.
  **The COST, recorded rather than assumed away**: without installed dependencies, type resolution
  and library modelling degrade, which weakens taint tracking through framework boundaries in
  exactly the first-party code this feature exists to cover, and the owner directive names taint
  analysis specifically. **That cost is UNMEASURED here** (see the FR-004a field in the pre-merge
  verification below), because measuring it requires the job log from a run that did not happen.
- **FR-004b (how it may be revisited)**: any future install **MUST NOT** be placed in a job that
  both holds `security-events: write` and is reachable from an untrusted reference. Carried into
  `enforcement-recommendation.md` item 6b.

### FR-003 scope ceiling (T018), measured at this commit

```
git ls-files '*.js' '*.jsx' '*.ts' '*.tsx' '*.mjs' '*.cjs' | wc -l                 291
... | grep -vcE '^tests/'                                                          290
... | grep -cE '^frontend/src/'                                                    173
... | grep -cE '^frontend/tests/'                                                  101
... | grep -cE '^src/dashboard/'                                                     6
```

Every value matches the expected figure exactly; no delta to carry into a tier 3 denominator. The
ceiling is "every JavaScript and TypeScript file outside the root-anchored `tests/**/*` exclusion",
which is **wider than the two dashboards**: the remaining 10 files are root and `frontend/`
configuration plus four contract stubs under `specs/` that never ship.

### SC-012 matrix-job enumeration (T020, T038)

```
grep -n 'PER MATRIX VALUE' .github/workflows/pr-checks.yml
282:  # This job's status contexts are generated PER MATRIX VALUE: the job is named

grep -n 'matrix:' .github/workflows/pr-checks.yml
302:      matrix:
```

**Enumerated, not asserted**: the workflow contains exactly **one** `matrix:` key, at line 302,
and it belongs to the `codeql` job (block at lines 291 to 326), which is the job now carrying the
warning. There is therefore **no other job** whose status context is generated per matrix value,
so SC-012's second clause is satisfied by exhaustion rather than by "none found". The
`PER MATRIX VALUE` comment appears exactly once and sits above `codeql:` at line 291, not above any
other job.

---

## Pre-merge verification (refs/heads/001-codeql-coverage)

**Every field in this section is NOT RUNNABLE. The single blocking dependency is the same one:
the branch is not on `origin`, pushing is owner-gated and unauthorised, so T022's dispatch never
happened and no branch analysis or job log exists to read.**

T022's own routing covers this case: SC-002, SC-003 and SC-007 move to the post-merge
`refs/heads/main` run at Phase E. That substitution is recorded here as instructed. It is a
deferral of the measurement, not a substitute for it.

- **Analysis id**: NOT RUNNABLE (no dispatch). Nothing to exclude, so FR-019's exclusion is vacuous
  rather than satisfied. When the run does happen, its id must be recorded here followed literally
  by `<- EXCLUDED from baseline capture per FR-019`, and T036's baseline must name a DIFFERENT id.
- **SC-002 results count**: NOT RUNNABLE (no branch analysis exists to read a `results_count` from).
- **SC-003 extracted files**: NOT RUNNABLE (no job log). **Recorded as UNPROVEN, which is the only
  permitted absent-evidence value.** `frontend/` UNPROVEN, `src/dashboard/` UNPROVEN, carried as an
  OPEN ITEM. **There is no `no` value.** Writing "no" would assert a coverage gap that was never
  observed, which is the one recording SC-003 forbids. UNPROVEN does not fail the MERGE gate.
- **SC-007 leg duration / workflow total / pre-change total**: NOT RUNNABLE / NOT RUNNABLE /
  5 to 7 min (the pre-change figure is the only one of the three that exists).
- **FR-004a resolution warnings observed in the job log, with the return code**: NOT RUNNABLE.
  **Not "none found".** There is no log, so there is no return code, and "none found" here would be
  the precise failure FR-004a's return-code requirement exists to prevent: an absent measurement
  rendering as a clean one.
- **FR-018 evidence-source audit (T029)**: **PASS.** No claim of coverage anywhere in this log rests
  on a pull request check. Verified by grep over this file; the only occurrences of pull-request
  terms are the statements that such evidence is BARRED, which is what the pass condition permits.
- **FEATURE STATUS: OPEN (FR-023). MERGE gate NOT evaluated: the pull request was never opened and
  the branch was never pushed. CLOSE-OUT gate pending.**
  The literal line T031 specifies, `FEATURE STATUS: OPEN (FR-023, MERGE gate passed, CLOSE-OUT gate
  pending)`, is **deliberately not written**, because the MERGE gate did not pass. It was not
  evaluated. Recording it as passed would be the FR-016b failure mode reached by a different route.

---

## Baseline record

**NOT RUNNABLE in full. Blocking dependency: Phase E is "after merge only" and the merge did not
happen. T033 requires the FIRST `refs/heads/main` JavaScript/TypeScript analysis, and no such
analysis exists: measured at AR#3, every one of the 948 analyses on `refs/heads/main` is
`/language:python`.**

Two fields below are NOT blocked and are written now, because they are the fields whose whole
purpose is to be written before the data arrives.

- **Source analysis id (refs/heads/main)**: NOT RUNNABLE (T033).
- **Analysis timestamp**: NOT RUNNABLE | **Close-out date (+10 working days)**: NOT RUNNABLE, and
  it is NOT guessed. A close-out date computed from an analysis that does not exist would be a
  deadline with no start, which is the exact defect FR-021 exists to close.
- **Accountable role for triage**: **Admin Role (Project Owner: @traylorre)**, cited to
  `CONTRIBUTING.md:64`, whose listed responsibilities already include "Respond to security
  incidents" (`CONTRIBUTING.md:74`). Recorded with the citation, not as a bare handle. **This field
  is not blocked and is final.**
- **Open alert count before: 5** | **after**: NOT RUNNABLE | **delta**: NOT RUNNABLE.
  The "before" half IS measured (T008, below) and is the artifact that makes SC-005's second clause
  checkable later. **When the "after" half arrives, FR-014's framing is mandatory**: the delta is
  recorded as *newly revealed pre-existing exposure*, never as a regression this feature introduced.
  The alerts were always there; until now nothing was looking. **An increase satisfies SC-004.**
- **FR-004a resolution warnings carried forward**: NOT RUNNABLE (nothing to carry).
- **Partition check**: NOT RUNNABLE.

### T008 pre-change capture (RUN, 2026-07-31), keyed on `(rule identifier, file path)`

`gh api ".../code-scanning/alerts?ref=refs/heads/main&state=open&per_page=100" --paginate --slurp`,
`rc=0`, then jq over the file. `--paginate` without `--slurp` would have applied the aggregating
filter once per page; `--jq` is never passed alongside `--paginate` here for that reason.

**Positive anchor**, because a corpus floor alone does not defend against a mistyped field path:
`[.[][] | select(.most_recent_instance.location.path == null)] | length` returns **0**. Every alert
resolved a real path. A mistyped path would have returned null for every alert with jq still
exiting 0 and the floor still satisfied.

Count: **5**, matching F7's prediction.

| key (`rule@path`) | number | severity |
|---|---|---|
| `py/bad-tag-filter@scripts/regenerate-mermaid-url.py` | 147 | high |
| `py/clear-text-logging-sensitive-data@src/lambdas/ingestion/handler.py` | 150 | high |
| `py/clear-text-logging-sensitive-data@src/lambdas/ingestion/handler.py` | 149 | high |
| `py/clear-text-logging-sensitive-data@src/lambdas/ingestion/handler.py` | 148 | high |
| `py/clear-text-logging-sensitive-data@src/lambdas/shared/auth/oauth_state.py` | 144 | high |

**`rule@path` is NOT unique, and that is why SC-005's clause 2 must count WITH MULTIPLICITY.**
Three of the five alerts (148, 149, 150) share one key. jq's array `-` removes every occurrence of
each right-hand element, so a key dropping from three members to one subtracts away completely and
a `disappeared`-only test would report nothing. The T037 filter's `shrunk` bucket is what closes
that, and it is not decoration.

**Numbers are recorded as a lookup convenience only. Identity is the pair, never the number**:
remediating an alert spawns a fresh number at the rewritten line, so a number-keyed baseline would
show members vanishing purely as an artifact of the fixes the triage window exists to produce.

| Path class | Alerts | Rule ids | Severities | Disposition |
|---|---|---|---|---|
| Product: `frontend/src`, `src/dashboard` | NOT RUNNABLE | | | |
| Test: `frontend/tests` | NOT RUNNABLE | | | |
| Non-shipping: build config, `specs/` contract stubs | NOT RUNNABLE | | | |

- `WINDOW: 10 working days, ASSUMED, Deferral 2 unanswered at capture`
- **Window extension (FR-016a, at most ONE): used? no.**

### SC-006 (T038), RUN read-only, 2026-07-31, PRE-merge

Taken pre-merge rather than post-merge, which is a weaker position than the task intends and is
stated as such: it establishes the four contexts are unchanged **by this branch's edits**, not that
they survive a merge. The merge cannot change them, since nothing in this diff touches branch
protection or any ruleset (FR-015), but that is an argument, not the post-merge measurement.

```
gh api "repos/traylorre/sentiment-analyzer-gsk/branches/main/protection/required_status_checks"
{
  "contexts": ["Secrets Scan", "Lint", "Run Tests", "Playwright E2E Tests"],
  "checks":   ["Secrets Scan", "Lint", "Run Tests", "Playwright E2E Tests"],
  "n_contexts": 4,
  "n_checks": 4
}
```

Both floors met, neither field null, exactly the four F8 contexts unchanged in NAME and COUNT.
Both `.contexts` (deprecated but still populated) and `.checks[].context` are printed so a future
API-shape change is visible rather than silent. **CodeQL gates nothing**, before or after this
change: `Analyze (python)` is not among the four, and the change ADDS
`Analyze (javascript-typescript)` while renaming nothing.

---

## Close-out record

**NOT RUNNABLE in full. Blocking dependency: Phase F runs on the recorded close-out date, which is
computed from the T033 analysis, which requires the merge, which did not happen.**

- **Undispositioned count at window close, BEFORE the FR-016b default is applied: NOT RUNNABLE.**
  **This field is deliberately left as NOT RUNNABLE and NOT as `0`.** A `0` here would be false in
  the most dangerous available direction: it reads as "every baseline alert was dispositioned" when
  the truth is that no baseline exists. SC-008 is measured against this number and only this number.
- **Undispositioned set, verbatim**: NOT RUNNABLE.
- **FR-016b default applied to that set as `carded follow-up`**: NOT RUNNABLE.
- **Close-out outcome (SC-013)**: NOT RUNNABLE. Neither `COMPLETE` nor `FAILED CLOSE-OUT` is
  written, because both are claims about a triage window that never opened.
- **§9 registry entries written (T032)**: **DONE.** Two sequential entries in
  `docs/reference/TECH_DEBT_REGISTRY.md`, allocated AT WRITE TIME against the registry's
  then-highest value, which was read as `TD-023` immediately before writing:
  - **TD-024**: npm ecosystem absent from `.github/dependabot.yml`. Measured 2026-07-31: the file
    declares `pip`, `github-actions` and `terraform` and not `npm`, while 99 Dependabot alerts are
    open of which **82 are npm** and 17 are pip. §9 trigger: "dependency issues requiring future
    attention".
  - **TD-025**: the §10 local-SAST gap. `make sast` runs Bandit and Semgrep over `src/` only, so
    after this lands CodeQL covers `frontend/` and no local pre-push tier does. §9 trigger: "known
    limitations".
  - **Collision warning for whoever merges these**: `TD-024` is contested across sibling features
    in this campaign. The allocation above was correct at write time (`TD-023` was the highest
    value in the tree at that moment, and no sibling's registry edits are present in this
    worktree). Whichever of the campaign's branches merges SECOND must renumber. That is inherent
    to merge-order allocation and is not a defect in it; pre-reserving is what created the
    collision this rule exists to prevent.
  - The third, CONDITIONAL entry (the FR-016b lapse set) is **not owed**, because the lapse path
    cannot have fired: there is no window and no baseline.
- **§9(b) labelled GitHub issues: OUTSTANDING, not discharged, and the §9 obligation is therefore
  NOT complete.** §9(b) asks for a `tech-debt`-labelled GitHub issue per entry. That label does not
  exist in this repository (13 labels: `bug`, `documentation`, `duplicate`, `enhancement`,
  `good first issue`, `help wanted`, `invalid`, `question`, `wontfix`, `dependencies`, `python`,
  `github-actions`, `terraform`) and the owner has directed that it **NOT** be created and that no
  issues be raised against it, with the whole question audited once at the end of the campaign.
  No `gh label create` was run, no `gh issue create` was run, and no other label was substituted.
- **FR-023 final sweep (T045)**: **NOT PERFORMED, and correctly so.** T045 must not be performed at
  merge, let alone before one. Of the nine MERGE-gate criteria, three carry a recorded outcome
  (SC-009 and SC-010 from B1; SC-006 from the pre-merge read above) and six do not. Of the four
  CLOSE-OUT criteria, none does. `FEATURE STATUS` stays **OPEN**.
