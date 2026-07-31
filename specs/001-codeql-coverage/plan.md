# Implementation Plan: CodeQL Coverage Expansion

**Branch**: `001-codeql-coverage` | **Date**: 2026-07-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-codeql-coverage/spec.md`

## Summary

Add `javascript-typescript` to the CodeQL analysis matrix so the customer dashboard
(`frontend/`) and the admin dashboard (`src/dashboard/`) are analyzed at all, and resolve the
self-contradiction between `paths-ignore` and `query-filters` in the shared CodeQL config.

Two files change: `.github/workflows/pr-checks.yml` (one matrix value plus the FR-022 warning
comment) and `.github/codeql/codeql-config.yml` (whatever the probe determines). Everything else
this feature delivers is process: an empirical probe, a baseline, a triage window, and an
enforcement recommendation.

The whole feature is about ORDER. The change itself is two lines. The risk is running the probe
and the baseline in the same dispatch, or running a probe whose control arm was never established.
The Execution Sequence below is the deliverable that matters most.

## Technical Context

**Language/Version**: No application language changes. Edited files are GitHub Actions workflow
YAML and CodeQL config YAML. Languages newly ANALYZED: TypeScript 5.x and JavaScript ES2022 under
`frontend/` and `src/dashboard/`, joining Python 3.13.
**Primary Dependencies**: `github/codeql-action` v4 (`init`, `autobuild`, `analyze`) with the
`security-extended` query suite and the shared config at `.github/codeql/codeql-config.yml`;
GitHub code scanning `analyses` and `alerts` REST APIs, read via `gh`. No application dependency
is added, and no dependency install runs inside the analysis job (FR-004a, FR-004b).
**Storage**: N/A. Alert and analysis state lives in GitHub code scanning. This feature's records
are markdown committed under `specs/001-codeql-coverage/`.
**Testing**: No unit or integration tests, because no runtime code changes. Verification is
API-observable: the `analyses` record on a `refs/heads/*` reference, the `alerts` API, and the
analysis job log. Pull request check results are barred as evidence (FR-018, F5, F6).
**Target Platform**: GitHub-hosted `ubuntu-latest` runners on a public repository.
**Project Type**: CI configuration change plus a documented process. No source tree changes.
**Performance Goals**: The `javascript-typescript` leg completes within 8 minutes AND total
workflow wall clock stays within 2 minutes of the pre-change 5 to 7 minutes. If the two bounds
disagree, the total bound governs (SC-007).
**Constraints**: No new merge gate and no change to the four required contexts (FR-015, SC-006).
No dependency install in a job that both holds `security-events: write` and is reachable from an
untrusted reference (FR-004b). Probe mutations never reach `main` (FR-010a). The probe and the
baseline never share a run (FR-019). No new AWS resources.
**Scale/Scope**: About 47,300 lines newly analyzed (`frontend/src` 22,295, `frontend/tests`
19,913, `src/dashboard` 3,996) plus about 745 lines of build configuration and contract stubs
under `specs/`. This paragraph IS the explicit scope ceiling FR-003 requires to be stated in this
feature's artifacts rather than discovered from the first result set: the effective scope is every
JavaScript and TypeScript file outside the root-anchored `tests/**/*` exclusion, which is wider
than the two dashboards. Two configuration files edited, one registry file appended, two to three
records committed.

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after the design below. Result unchanged in both
passes, because the design adds no code and no dependency.*

| Constitution section | Applies how | Result |
|---|---|---|
| §3 Security & Access Control ("include SAST and secret scanning in CI") | This feature widens SAST coverage from one language to two and from about 0 to about 48,000 lines of previously unanalyzed JavaScript and TypeScript. | **PASS**, strengthened |
| §7 Testing & Validation | No runtime code changes, so no unit or integration tests are owed. Amendment 1.5's ISO 8601 date rule applies to every date written into this feature's records. | **PASS** (no tests owed; date format binding) |
| §8 Git Workflow & CI/CD (pre-push, GPG signing, feature branch) | Standard. All commits GPG-signed, work on `001-codeql-coverage`, `make validate` before push. | **PASS** |
| §8 Pipeline Check Bypass (ABSOLUTE RULE) | This feature adds a status context and removes none. It does not touch branch protection, does not mark anything as expected-to-fail, and SC-006 verifies the four required contexts are unchanged in name and count. | **PASS** |
| §9 Tech Debt Tracking (registry + GitHub Issues for deferred items) | **CORRECTED at Clarification Q2.** The registry EXISTS, at `docs/reference/TECH_DEBT_REGISTRY.md` (`TD-001` to `TD-023`), relocated from the flat path by `f8db8d2` (PR #668); §9's path at constitution lines 527, 569 and 584 is stale, the file is not missing. Of the deferred items, three are genuine debt owing entries (npm ecosystem, the §10 local-SAST gap, any FR-016b lapse set) and three are carded follow-ups only (required-check promotion, concurrency-cancel group, `frontend/tests` symmetry). See the Q2 triage table in spec.md. | **PASS with obligation**, carried into Phase F |
| §10 Local SAST Requirement | `make sast` runs Bandit over `src/` and Semgrep `--config auto` over `src/` only. `src/dashboard` therefore gains some local overlap; `frontend/` gains none. The stated acceptance criterion is scoped "≥70% coverage of CodeQL patterns **for Python**", so nothing is violated. | **PASS**, with a recorded gap |

**Recorded gap (§10)**: after this feature lands, CodeQL covers `frontend/` but no local pre-push
tier does. That is a widened CodeQL-versus-local asymmetry, not a regression, and it is carried
into the FR-017 enforcement recommendation alongside the two questions FR-017a already names.

## Project Structure

### Documentation (this feature)

```text
specs/001-codeql-coverage/
├── spec.md                         # Input, 897 lines, includes Adversarial Review #1 and the
│                                   #   2026-07-30 Clarifications session (Q1 to Q5, 2 DEFERRALS)
├── plan.md                         # This file
├── quickstart.md                   # Operator runbook: exact commands per step, plus the
│                                   #   field skeletons for the two records below
├── checklists/                     # Pre-existing
├── evidence-log.md                 # Created during execution. Four sections, each naming its
│                                   #   analysis identifier: probe record (FR-010), pre-merge
│                                   #   verification, baseline record (FR-013/019/020/021),
│                                   #   close-out outcome (SC-013)
└── enforcement-recommendation.md   # Created at close-out. FR-017, FR-017a, SC-011
```

**Deliberately not created.** `research.md`: every open question was already settled in spec.md's
F1 through F18 and its adversarial review; a research file here would restate them. The handful of
genuinely open design questions are settled inline under Design Decisions below. `data-model.md`:
this feature has no entities. `contracts/`: this feature exposes no interface, and per F15 adding
files under `specs/` would enlarge the very scan scope this feature is measuring.

### Files changed (repository)

```text
.github/workflows/pr-checks.yml       # Job "codeql" (name: Analyze), line 294 at c010178: matrix
                                      #   gains 'javascript-typescript'. Job header gains the
                                      #   FR-022 matrix-context warning comment.
.github/codeql/codeql-config.yml      # paths-ignore / query-filters resolved per FR-011 at B3.
                                      #   The comment at line 13 is FALSE per Q4 and is removed.
                                      #   No RULE changes without a B2 result (FR-008).
docs/reference/TECH_DEBT_REGISTRY.md  # Two sequential entries at D2 for the npm ecosystem gap and
                                      #   the §10 local-SAST gap. Identifiers allocated at merge
                                      #   time, never pre-reserved. Plus a `tech-debt` issue each.
```

**Structure Decision**: no source structure applies. The unit of change is two CI configuration
files plus committed records in this feature's directory.

## Design Decisions

Settled here so the implementer does not rediscover them mid-run.

- **D-1. One matrix value, not two.** Use the combined identifier `javascript-typescript`.
  TypeScript is analyzed by the JavaScript extractor with TypeScript enabled by default, and
  GitHub's own detection for this repository already names the combined identifier (F9, FR-001).
- **D-2. Keep the `autobuild` step unconditional.** It is a no-op for JavaScript and TypeScript,
  so conditionalizing it adds a branch that buys nothing. If the first run contradicts that, FR-004
  governs: state the prerequisite explicitly and provision it, do not work around it.
- **D-3. No dependency install, and the cost is stated rather than assumed away.** Per F17 the
  analysis job holds `security-events: write` and triggers on `pull_request` on a public
  repository. An install there would execute contributor-authored package lifecycle scripts inside
  that job. The cost of omitting it is real and lands on this feature's own purpose: without
  installed packages, type and library resolution degrade, which weakens taint tracking through
  framework boundaries in first-party code. FR-004a requires the baseline record to note whether
  the job log emitted type-resolution or module-resolution warnings, so a future revisit is
  evidence-backed rather than a re-argument.
- **D-4. The config is shared across both legs, and FR-006 resolves in two parts.** The
  `query-filters` entry names `py/incomplete-url-substring-sanitization`, a Python rule id that
  cannot match any JavaScript or TypeScript rule, so it is INERT for the new leg. The
  `paths-ignore` entry is genuinely language-neutral and DOES apply to the new leg. Both facts go
  into the FR-006 record. The root-anchored `tests/**/*` pattern reaches `tests/load/api-load-test.js`
  and does NOT reach `frontend/tests` (F15). Per A2 and FR-007/FR-007a, `frontend/tests` stays in
  scope and the resulting asymmetry against excluded Python test code is argued or carded in the
  evidence log, never left undiscussed.
- **D-5. The probe runs Python-only.** Two reasons. It keeps each arm a single-variable comparison,
  and it makes FR-019 structurally true rather than a discipline anyone has to remember: a
  Python-only run cannot produce a JavaScript/TypeScript result set to accidentally baseline.
- **D-6. Keep `category: "/language:${{matrix.language}}"` unchanged.** Per-language categories are
  what let SC-001 (a JavaScript/TypeScript entry exists) and SC-005 (Python still reports at least
  9 results) be checked independently. A shared category would collapse them into one number.
- **D-7. FR-022 warning comment.** Modeled on the existing `playwright-e2e` warning at
  `.github/workflows/pr-checks.yml:390-394`. Proposed text, to be placed in the `codeql` job
  header:

  ```yaml
  # This job's status contexts are generated PER MATRIX VALUE: the job is named
  # "Analyze" and reports as "Analyze (python)" and "Analyze (javascript-typescript)",
  # one context per language. Editing or removing a matrix value RETIRES the
  # corresponding context. Nothing requires these contexts today, so nothing breaks
  # right now. If CodeQL is ever promoted to a required check, branch protection will
  # name the per-language string and a later matrix edit would silently retire the
  # context that names it. Do not edit this matrix without checking required status
  # checks in the same change.
  ```

## Execution Sequence

Each step names what it PROVES and what it PRODUCES. Steps run in this order. The ordering
constraints are load-bearing: B1 before B2 (the evidence record exists before any arm is
considered, and B1 alone is what satisfies SC-009 and SC-010), all of B before C (FR-019, D-5), and
C before E (a baseline must come from the configuration that ships).

### Phase A. Pre-flight

**A1. Confirm manual workflow dispatch on the feature branch is available.**
*Proves*: whether the probe is runnable at all. Feature-branch pushes alone do not trigger the
workflow (F12) and a pull request run cannot answer the question (F5).
*Produces*: a yes or no recorded in the evidence log.
*If no*: FR-009c applies, but its bite is much smaller after Q4 than it was when it was written.
The config question itself is already settled from an existing `refs/heads/main` log, so B1 runs
regardless. What a missing dispatch costs is only the OPTIONAL B2 arm, which is recorded NOT RUN
and resolves by FR-009b's retain-unchanged default. FR-008's prohibition on rule changes still
holds. User Story 1 falls back to the post-merge `refs/heads/main` run for all its evidence, which
means SC-002, SC-003 and SC-007 are evaluated post-merge rather than pre-merge. Keep B1 and B3,
skip B2, go to Phase C.

**A2. Snapshot the 5 currently open Python alerts as (rule identifier, file path) PAIRS, before
anything changes.**
*Proves*: nothing on its own. It is the only thing that makes SC-005's second clause checkable
later. "No previously open Python alert disappears as a side effect" cannot be evaluated after the
fact without a pre-change list, and the spec assumes that list without requiring anyone to take it.
*Identity*: rule plus path, NEVER the alert number. Numbers are not stable across remediation,
because closing an alert and rewriting the line spawns a fresh number at the same location, so a
number-keyed comparison reports a loss that did not happen. Record the numbers as a lookup
convenience, but do not compare on them. The alerts API exposes nothing finer than path and line
and column offsets under `most_recent_instance.location`, so rule plus path is the strongest
identity mechanically available and SC-005 asks for no more.
*Produces*: the pre-change open-alert list in the evidence log, keyed on rule and path.

**A3. Record the two Clarification DEFERRALS and route each one.** The clarification session left
exactly two owner decisions open. Neither has a home outside the spec's Clarifications appendix,
which is where deferrals go to expire, so each is given a destination here.

*Deferral 2, the window duration (spec.md Q5).* This one is LOAD-BEARING and it has a deadline.
A1 and FR-021 compute a calendar close-out date from "10 working days" and write it into the
baseline record at capture time, and FR-016a permits exactly ONE extension. If the owner answers
after E2 has written the date, the only available correction is that single extension, spent on an
authoring artifact instead of on alert volume. So: ask before E2. If unanswered by E2, record 10
working days as ASSUMED rather than confirmed, say so in the baseline record, and treat any later
owner change as the FR-016a extension it is.
*Deferral 1, the stale constitution §9 path (spec.md Q2).* Not blocking and not this feature's to
fix. It is carried as a question inside the F2 enforcement recommendation, so it reaches the same
named decider under the same decision-by date rather than sitting in an appendix.

*Produces*: both deferrals recorded in the evidence log with their status and their destination.

### Phase B. Config resolution (config only, matrix untouched, Python-only)

**AMENDED at Clarification Q2 and Q4. The three-arm probe this phase originally carried is
superseded and MUST NOT be run.** FR-009b now states that arms 1 and 2 are ANSWERED from
extraction-level evidence already present in a `refs/heads/main` full-tree job log, and that
running them would mutate the shared config to re-derive a settled fact. At most ONE arm survives
and it is OPTIONAL. Every step below is admissible under FR-009 because its source is a branch
reference, never a pull request reference.

**B1. Transcribe the Q4 evidence into the probe record.** No dispatch. No config mutation.
*Proves*: FR-010, SC-009 and SC-010 by the evidence route FR-009b now permits, rather than by an
arm comparison.
*Produces*: the probe record's evidence section in `evidence-log.md`, naming the run identifier
`30581930915`, job `91004036909`, and the three log lines that carry the finding: the extractor
invoked with `--filter exclude:tests/**/*` (line 1480), zero of 152 `Extracted file` lines under
`/tests/` (from line 1487), and the coverage summary "scanned 152 out of 154 Python files"
(line 2067). Also the FR-006 record: the `query-filters` entry names a `py/` rule identifier that
cannot match any JavaScript or TypeScript rule and is INERT for the new leg, while `paths-ignore`
is genuinely language-neutral and DOES apply to it (D-4).

**B2. OPTIONAL control arm.** Run it for exactly one purpose: to decide whether to DELETE the inert
query filter as dead or RETAIN it against a future narrowing of the path exclusion. Remove BOTH
`paths-ignore: tests/**/*` and the `py/incomplete-url-substring-sanitization` query filter, then
dispatch a full-tree Python-only run on `refs/heads/001-codeql-coverage`.
*Proves*: whether the filtered rule still fires on current Python test code at all. Per F4, six of
the eight historical alerts for that rule are `fixed`, so it may fire on nothing.
*Produces*: the arm's analysis identifier, its verbatim config, and its result count and paths
under `tests/`, read from that analysis's SARIF and never from the alerts endpoint. An alert
carries only `most_recent_instance`, which a later run on the same reference overwrites, so an
alerts-API read cannot separate one run from another.
*If NOT RUN, or if it returns zero results under `tests/`*: FR-009b's stated default governs. The
query filter is RETAINED unchanged, because deleting a rule without evidence is exactly what FR-008
forbids. Record the arm as NOT RUN or INCONCLUSIVE. Neither outcome blocks the feature and neither
fails SC-009 or SC-010, which B1 already satisfies.

**B3. Revert any mutation made in B2 and apply the FR-011 resolution.** If B2 was not run there is
nothing to revert. The resolution is wording in every case that Q4 has already settled: the comment
at `.github/codeql/codeql-config.yml:13` claiming "All other security rules apply to tests" is
FALSE and is removed, the stated intent is made explicit, and no rule is added or deleted except on
the strength of a B2 result. FR-012 binds this edit: the resolution MUST NOT reduce Python analysis
coverage below the F7 baseline for any rule other than the single deliberately filtered one.
*Proves*: FR-010a (no arm reaches `main`), FR-011, FR-012, SC-009.
*Produces*: the final content of `.github/codeql/codeql-config.yml`.

### Phase C. Matrix change

**C1. Add `javascript-typescript` to the matrix and add the D-7 warning comment.** The config is
already in its final landed state from B3.
*Proves*: FR-001, FR-002 (`fail-fast: false` is already set, so one leg failing cannot cancel the
other), FR-005 (both legs share `queries: security-extended`), FR-022.

**C2. Dispatch a full-tree run on `refs/heads/001-codeql-coverage`.**
*Proves*: SC-002 (the leg runs and reports a results count), SC-003 (the job log records extracted
sources under BOTH `frontend/` and `src/dashboard/`, so this is not a one-dashboard win),
SC-007 (leg wall clock and workflow total), A3/FR-004 (no build step needed).
*Produces*: the pre-merge verification section of `evidence-log.md`, including the analysis
identifier, and the FR-004a note on type-resolution and module-resolution warnings from the job
log. This identifier is recorded so FR-019 can EXCLUDE it from baseline capture by identifier.

### Phase D. Merge

**D1. Open the pull request and merge it.** MERGE gate per FR-023: SC-001, SC-002, SC-003, SC-005,
SC-006, SC-007, SC-009, SC-010, SC-012. SC-001 and SC-005 are satisfied by the first
`refs/heads/main` run immediately after merge, which is why the gate reads "at merge, plus the
first `refs/heads/main` run".
*The feature status stays OPEN.* Closing here is the failure mode FR-016b names.

**D2. Discharge the §9 registry obligation for the two UNCONDITIONAL debt items.** The Constitution
Check above records §9 as **PASS with obligation** after Clarification Q2 withdrew the deviation.
An obligation with no execution step is the same defect AR#1 finding 1 caught elsewhere, so it gets
one here. Two of the three items in the Q2 triage are unconditional and are owed at merge, not at
close-out: the npm ecosystem absent from `dependabot.yml` while 82 npm advisories are open (F18),
and the §10 local-SAST gap this feature widens (recorded above the Constitution Check). Each gets a
sequential entry in `docs/reference/TECH_DEBT_REGISTRY.md`, per constitution §9(a). §9(b)'s labelled
issue is NOT raised: the owner has directed that the `tech-debt` label not be created, so that half
is recorded as outstanding rather than discharged. The third item, an FR-016b lapse set, is
conditional and belongs to F3.
*Identifier allocation*: AT MERGE TIME, in merge order, against the registry's then-highest value.
Never pre-reserved. `TD-024` is already claimed by `001-oauth-provider-taint` and contested by
`001-ruff-bump-forward`, and pre-reserving is what created that collision.
*Proves*: the Constitution Check §9 row, which is otherwise an assertion nobody discharges.

### Phase E. Baseline

**E1. Capture the FIRST `refs/heads/main` JavaScript/TypeScript analysis** produced by the
post-merge push.
*Proves*: SC-001. This identifier, and no other, starts the triage clock under A1.

**E2. Write the baseline record** into `evidence-log.md`: count, rule identifiers, severities,
file paths, partitioned into path classes (product `frontend/src` and `src/dashboard`; test
`frontend/tests`; non-shipping build configuration and contract stubs under `specs/`), the open
alert delta against the pre-change 5, the FR-004a resolution-warning note, the named accountable
role, the source analysis identifier, and the close-out date in ISO 8601 computed as 10 working
days from that analysis.
The delta is recorded as newly revealed pre-existing exposure, never as a regression this feature
introduced, and a rise in the open count is the EXPECTED outcome rather than a failure condition
(FR-014, SC-004, and the owner directive quoted at the top of spec.md).
*Proves*: FR-013, FR-014, FR-019, FR-020, FR-021, SC-002, SC-004.

**E3. Verify no collateral damage.** Python analysis on `refs/heads/main` reports at least 9
results and no previously open Python alert flipped to `fixed` as a side effect of the config work
(SC-005, a floor and not an equality). The required status check set still contains exactly the
four contexts from F8 (SC-006). The workflow contains no other matrix-context job lacking a
warning (SC-012).

### Phase F. Close-out

**F1. Disposition every baseline alert** within the window: fix now, carded follow-up, or
dismissed with a recorded reason. One bulk disposition may cover a whole path class where the rule
identifier and the reason are identical across it (FR-020). The window may be extended exactly
once, to a new fixed date recorded alongside its reason (FR-016a).
*Proves*: SC-008.

**F2. Write `enforcement-recommendation.md`**: severity threshold, path scope, blocking or
non-blocking position, the role that decides, and a decision-by date, justified by the observed
volume. It must also cover the `frontend/tests` symmetry question (FR-007a, already ARGUED at Q4
and carded, so this is a transcription rather than a fresh argument), the FR-004b install
constraint, the §10 local-SAST gap recorded above, and the A3 Deferral 1 question of whether
constitution §9's stale path is amended or the registry moved back.
*Proves*: FR-017, FR-017a, SC-011.

**F3. Record the close-out outcome** as COMPLETE or FAILED CLOSE-OUT. **The order of the three
actions below is load-bearing and was made so at Clarification Q5.** SC-008 is evaluated BEFORE
FR-016b's default is applied, because after the default every alert carries a disposition by
construction and the criterion could never fail.

1. **COUNT FIRST.** At window close, count the undispositioned baseline alerts and record the
   number verbatim in the close-out record, INCLUDING when that number is zero. This number, and
   only this number, is what SC-008 is measured against.
2. **THEN default.** Every undispositioned alert is recorded as `carded follow-up`, so the count
   never silently drops.
3. **THEN record the outcome.** A non-zero count at step 1 means FAILED CLOSE-OUT, and one
   follow-up item is raised carrying the undispositioned set: a sequential entry in
   `docs/reference/TECH_DEBT_REGISTRY.md`, identifier allocated at merge order per D2, with §9(b)
   recorded as outstanding for the reason given there. A zero count means COMPLETE.

*Proves*: SC-013, FR-016b, and the conditional third item of the Q2 §9 triage. CLOSE-OUT gate per
FR-023: SC-004, SC-008, SC-011, SC-013.

## What Can Still Go Wrong

| Hazard | Where it bites | Mitigation in this plan |
|---|---|---|
| Probe and baseline share a run | A baseline of a configuration that never shipped | D-5 makes the probe Python-only, so it structurally cannot emit a JavaScript/TypeScript result set. C2's identifier is recorded specifically so FR-019 can exclude it. |
| All-zero arm read as a conclusion | A rule change made on an artifact | B2 is optional, single-purpose, and its zero outcome resolves to RETAIN, never to DELETE (FR-009b). B1 carries the finding, so no rule change ever depends on an arm count. |
| Q4's collapse of the probe silently voids the merge gate | SC-009 and SC-010 unsatisfiable when B2 is skipped | Both criteria amended to accept B1's transcribed extraction evidence as the traceability and reproducibility source |
| §9 obligation asserted but never discharged | Constitution Check row is false at merge | D2 writes the two unconditional registry entries; F3 carries the conditional third |
| Feature closed at merge | SC-008 and SC-011 never evaluated | FR-023 two-gate table, restated at D1 |
| Alert volume swamps the window | FR-016 becomes arithmetically unmeetable | FR-020 path-class bulk disposition at E2, before triage starts, not after |
| Degraded taint tracking goes unnoticed | The feature's own purpose quietly underdelivers | FR-004a note captured at C2 from the job log and carried into E2 |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **WITHDRAWN at Clarification Q2.** The §9 deviation previously recorded here rested on the claim that `docs/TECH_DEBT_REGISTRY.md` "does not exist anywhere in this repository". That claim was false. | The registry exists at `docs/reference/TECH_DEBT_REGISTRY.md`; only the constitution's path reference is stale. §9 is satisfiable, so there is no deviation to justify. | No alternative needed. The obligation is now live: Phase F writes registry entries for the three items the Q2 triage classes as genuine debt. The `TD-` identifier is allocated AT MERGE TIME against the registry's then-highest value, NOT pre-reserved, because `TD-024` is already claimed by `001-oauth-provider-taint` and contested by `001-ruff-bump-forward`. |

## Adversarial Review #2

**Reviewer**: adversarial reviewer, did not author this spec, this plan, or AR#1.
**Date**: 2026-07-30.
**Scope**: DRIFT introduced by the Stage 4 clarification answers, and cross-artifact consistency
across `spec.md` (860 lines pre-review), `plan.md`, `quickstart.md`, and
`checklists/requirements.md`. AR#1's own findings were not re-litigated except where a
clarification answer later undermined the fix.

**Method note.** `/speckit.clarify` writes answers into `spec.md` and revisits nothing else. Five
questions were answered and five requirements or criteria were changed. This review treated every
one of those five as a suspected write-through failure into the other three artifacts, then
checked the reverse direction: whether the answer left the ANSWERING file self-consistent. Both
directions produced findings.

### Findings

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| 1 | CRITICAL | **`plan.md` instructs the implementer to do what `spec.md` forbids.** Clarification Q4 (`spec.md:801-806`) amended FR-009b (`spec.md:286-297`): "Arms 1 and 2 are ANSWERED and MUST NOT be run, because running them would mutate the config to re-derive a settled fact", and the surviving control arm became OPTIONAL. `plan.md:174-204` still ran the full three-arm probe as B1, B2, B3, each arm a committed mutation of the shared config. `quickstart.md:47-52` carried the three-arm run-order table and `quickstart.md:53-57` the `probe(001): codeql config arm N` commit loop. An implementer following the plan literally commits two config mutations that FR-008 and FR-009b both bar. This is the most direct plan-versus-spec contradiction in the campaign: not a stale sentence, an instruction. | FIXED. Phase B rewritten as B1 (transcribe the Q4 extraction evidence, read-only), B2 (OPTIONAL single-purpose control arm), B3 (revert and apply FR-011). `quickstart.md` Phase B rewritten to match, with the arm table restated as a status table marking arms 1 and 2 MUST NOT run. |
| 2 | CRITICAL | **Q4 silently made two MERGE-gate criteria unsatisfiable.** SC-009 required every retained rule to be "traceable to a line in the probe record"; SC-010 required a second person to "name the analysis identifiers, re-run the comparison, and reach the same conclusion". Both were written against a mandatory three-arm probe. After Q4 the only arm is OPTIONAL, so on the exact path FR-009b permits there are no arms, no analysis identifiers, and no comparison. FR-023's MERGE gate (`spec.md:389`) lists SC-009 and SC-010, so a literal reading blocks merge on the permitted path. Q4's own "Effect on requirements" (`spec.md:801-806`) lists FR-009b as changed and never mentions the two criteria that depended on it. | FIXED. SC-009 and SC-010 amended in `spec.md` to accept EITHER an arm line, where the arm was run, OR the transcribed Q4 extraction evidence (run `30581930915`, job `91004036909`, log lines 1480, 1487, 2067). Both keep teeth: an empty probe record satisfies neither form. |
| 3 | HIGH | **The withdrawn §9 deviation created a live obligation that no execution step discharges.** Q2 (`spec.md:707-718`) withdrew the deviation and produced a triage naming THREE genuine debt entries. `plan.md:59` then recorded §9 as "**PASS with obligation**, carried into Phase F", and `plan.md:282` asserted "Phase F writes registry entries for the three items". Phase F had exactly three steps, F1 disposition, F2 enforcement recommendation, F3 close-out outcome, and none of them wrote a registry entry or opened an issue. The "Files changed (repository)" block listed two files and did not list `docs/reference/TECH_DEBT_REGISTRY.md`. `quickstart.md` had no registry step and no `gh issue create` anywhere. Withdrawing a deviation converted a justified gap into an unmet requirement. Worse, two of the three items are UNCONDITIONAL and therefore owed at merge, not at close-out, so deferring all three to Phase F was wrong even had Phase F had a step. | FIXED. New step D2 writes the two unconditional entries (npm ecosystem, §10 local-SAST gap) with merge-time identifier allocation; F3 carries the conditional FR-016b lapse entry. Registry added to the Files changed block. `quickstart.md` gains a Phase D section with the identifier-allocation command. |
| 4 | HIGH | **Both DEFERRALS were recorded only inside the Clarifications appendix, with no owner-facing route and no trigger.** Neither appears in `plan.md`, `quickstart.md`, or the spec's own "Carded, raised with the owner" list at `spec.md:553-565`, which is the feature's actual owner channel. Deferral 1 (§9 stale path) had no decision-by date and no destination. Deferral 2 (the 10-working-day window) is worse than undelivered, it is LOAD-BEARING with a deadline: A1 (`spec.md:506-512`) and FR-021 (`spec.md:337-343`) compute a calendar close-out date from that duration and write it into the baseline record AT CAPTURE TIME, and FR-016a permits exactly ONE extension. An owner answer arriving after E2 would spend that single extension on an authoring correction rather than on alert volume, which is precisely the scarcity FR-016a was designed to protect. Nothing sequenced the question before E2. | FIXED. Both added to `spec.md`'s carded Out of Scope list with their status. New `plan.md` step A3 routes Deferral 2 as blocking-for-Phase-E with a stated ASSUMED fallback, and Deferral 1 into the F2 enforcement recommendation so it inherits that document's named decider and decision-by date. `quickstart.md` Phase A gains the same. F2's required contents updated. |
| 5 | HIGH | **`plan.md` F3 dropped the ordering that Q5 made load-bearing.** Q5 (`spec.md:838-842`) found SC-008 vacuous and restated it (`spec.md:448-453`) to be measured at window close BEFORE the FR-016b default is applied, and FR-016b (`spec.md:356-365`) now requires "the undispositioned set is FIRST counted and recorded verbatim". `plan.md:262-266` stated the default first and never mentioned counting, so an implementer following the plan reproduces exactly the vacuity Q5 removed. | FIXED. F3 rewritten as three explicitly numbered, explicitly ordered actions: COUNT FIRST, then default, then record the outcome, with the reason stated inline so a later reader does not re-collapse them. |
| 6 | HIGH | **`quickstart.md`'s close-out skeleton had no field for the number SC-008 is measured on.** SC-008 (`spec.md:452-453`) requires "The undispositioned count at window close is written into the close-out record as a number, including when that number is zero." The skeleton at `quickstart.md:210-211` carried only the extension flag and the COMPLETE/FAILED value. The one number the criterion measures had nowhere to go, so the record could be filled in completely and still not satisfy SC-008. | FIXED. Skeleton gains the pre-default count field with the reasoning inline, plus a window-duration CONFIRMED/ASSUMED field for Deferral 2 and a §9 registry-entry field for D2. |
| 7 | HIGH | **`quickstart.md`'s SC-003 skeleton forced a binary the anti-false-negative rule forbids.** Q3 rewrote SC-003 (`spec.md:405-426`) with a three-tier ladder and an explicit rule: absence of evidence "MUST be recorded as SC-003 UNPROVEN ... MUST NOT be recorded as 'the admin dashboard was not extracted'". Q3 correctly fixed the broken `^frontend/` grep at `quickstart.md:108` and correctly added tier structure at `quickstart.md:111-124`, then left the record skeleton at `quickstart.md:189` reading `frontend/ yes|no, src/dashboard/ yes|no`. `no` is the exact recording SC-003 prohibits, and the skeleton offers no third value. The clarification fixed the measurement and missed the place the measurement is written down. | FIXED. Skeleton now offers PROVEN (with tier) or UNPROVEN, with "There is no `no` value" stated. |
| 8 | HIGH | **`quickstart.md` E2 captured the baseline from an unfiltered alerts query.** `quickstart.md:144-146` queried `alerts?ref=refs/heads/main&per_page=100` with no `state` and no rule filter. Two consequences. (a) The 5 pre-existing open Python alerts land inside a baseline that FR-016 and SC-008 define over the JavaScript/TypeScript set, inflating the disposition obligation with alerts `spec.md:544` puts explicitly Out of Scope. (b) A2 (`quickstart.md:34`) captured `state=open`; E2 captured all states, including the 15 dismissed and 117 fixed of F7. The SC-004 delta at `quickstart.md:201` therefore compared two different populations and would have reported a large fictitious increase, in a feature whose central claim is that a real increase is the expected outcome. A fake increase inside that framing is uniquely hard to catch. | FIXED. E2 query filtered to `state=open` and partitioned into `jsts` and `python` buckets in the same `jq`. |
| 9 | HIGH | **Five spec requirements were unreachable from `plan.md`.** Verified by extraction: `plan.md` cited no FR-003, FR-009, FR-009b, FR-012, or FR-014. FR-014 was at least reachable from `quickstart.md:216`; the other four appeared in NEITHER downstream artifact. FR-009b's absence is the mechanism behind finding 1: the plan could contradict the one requirement Q4 amended precisely because it never named it. FR-014 matters independently, because "a rising alert count is not a failure" is the owner-directive reading this whole feature rests on and the plan never said it. | FIXED. FR-003's scope ceiling now stated as such in Technical Context Scale/Scope; FR-009 admissibility stated at the head of Phase B; FR-009b named throughout the rewritten Phase B; FR-012 bound to the B3 config edit; FR-014 bound to E2's delta. |
| 10 | MEDIUM | **F1's line citation is wrong, and `plan.md` repeats it.** `spec.md:24` cited `.github/workflows/pr-checks.yml` line 319 for `language: ['python']`; the matrix is at line 294, both in the worktree and at `c010178`. `plan.md:93` said "~line 319". This is the single most-cited location in the feature and it pointed 25 lines past the thing it names. | FIXED, single line each. Both now cite line 294 at `c010178`, with the job block opener (282) added for anchoring. |
| 11 | MEDIUM | **`plan.md:72` described `spec.md` as 613 lines.** It is 860 pre-review. The count predates both the AR#1 appendix and the Clarifications appendix, and the tree comment named only AR#1. A reader budgeting from the plan underestimates the input by 40 percent, and 860 lines is itself the largest spec in the campaign. | FIXED, single line. Now 860 with both appendices named. |
| 12 | MEDIUM | **Q4 did not update `spec.md`'s own prose, so the file argues against its own fact table.** Three passages still assert the contradiction is unresolved. `spec.md:99-102` (US2 body): "may be dead as a result ... At most one of those three things is true. The engineer cannot tell which, and neither can anyone else, because the behaviour has never been probed." `spec.md:114-115` (acceptance scenario 2.1) opens "Given the contradiction is unproven". `spec.md:160-164` (edge case) states "the two readings of F3 remain indistinguishable". F3 at `spec.md:26` now says exactly which of the three claims is true and why. A reader arriving at US2 before reaching the appendix gets the pre-Q4 story. | RECORDED, not fixed. Three separate multi-sentence rewrites inside a section AR#1 also edited; the fact table and FR-009b already carry the correct state, and the risk of introducing a fourth inconsistency exceeds the benefit. Rewrite these three passages before implementation. |
| 13 | MEDIUM | **`spec.md:108` cites the wrong FR range for the probe.** US2's Independent Test says "Run the probe described in FR-007 through FR-009". FR-007 and FR-007a are the `frontend/tests` scope decision, not the probe. The probe is FR-008 through FR-010a. Pre-existing, survived AR#1, and now doubly misleading because FR-009b within that range has been amended to forbid most of what "the probe" used to mean. | RECORDED, not fixed. One-line correction to "FR-008 through FR-010a", deferred only because it sits inside the same US2 block as finding 12 and should be fixed in one pass with it. |
| 14 | MEDIUM | **`plan.md` D-4 and `quickstart.md` still task the implementer with deriving an argument Q4 already wrote.** Q4 (`spec.md:808-816`) supplies the FR-007a asymmetry rationale in full and states the disposition: preserved deliberately for this feature's duration, symmetry question stays carded, no TD entry per the Q2 triage. `plan.md:126-128` still says the asymmetry "is argued or carded in the evidence log", and the probe-record skeleton still asks for it as open work. That invites a second argument that may not match the first. | PARTLY FIXED. F2 now says the FR-007a coverage is a transcription of Q4 rather than a fresh argument. D-4 and the skeleton bullet left as authored; retarget them at Q4 before implementation. |
| 15 | MEDIUM | **`plan.md`'s Summary and framing still treat the probe as the feature's central unknown.** `plan.md:13` "(whatever the probe determines)", `plan.md:18-19` "The risk is running the probe and the baseline in the same dispatch, or running a probe whose control arm was never established. The Execution Sequence below is the deliverable that matters most." After Q4 the config question is settled from an existing log, the surviving arm is optional, and its default is fixed. The Execution Sequence is still the deliverable that matters most, but for the §9 obligation and the two-gate close-out, not for the probe. | RECORDED, not fixed. Phase A1 and Phase B, the operative text, were corrected; the Summary is framing. |
| 16 | MEDIUM | **`checklists/requirements.md` was never revisited after AR#1 or the clarifications.** AR#1 finding 19 (`spec.md:609`) recorded that it self-certifies items that were false at review time and deliberately left it as authored. It is still dated 2026-07-30, still shows all 16 boxes ticked, and `requirements.md:42` still reads "Items marked incomplete require spec updates before `/speckit.clarify` or `/speckit.plan`" when both have already run. It is the only artifact in the feature with zero traceability to the other three, and it certifies "Requirements are testable and unambiguous" over a spec in which two MERGE-gate criteria were unsatisfiable (finding 2) until this review. | RECORDED, not fixed. AR#1 made a deliberate decision to leave the file as authored and this review does not overturn it. Note that the decision is now weaker than when AR#1 made it: the certification has survived one adversarial review and one clarification session without being re-examined. |
| 17 | LOW | **Line-count inconsistency for the newly analyzed surface.** `plan.md:44` and F10 say about 47,300; `plan.md:55` says "about 0 to about 48,000"; `spec.md:618` and `spec.md:647` say "about 48,000". Measured is 47,298. | RECORDED. Harmless, but three figures for one measured number in one feature is how a fourth gets invented. |
| 18 | LOW | **`plan.md:136` cites the Playwright warning at `pr-checks.yml:390-394`.** The warning block is lines 389-393; 394 is the `# ====` rule and 395 opens `playwright-e2e:`. Off by one at both ends. | RECORDED. |
| 19 | LOW | **`spec.md:26` F3 cites `codeql-config.yml` "lines 19 to 30".** The file is 29 lines. Q4 at `spec.md:792` cites 23 to 29 correctly, so the spec contains both the wrong and the right citation for the same block. | RECORDED. |
| 20 | LOW | **Definition order no longer matches gate order.** SC-012 is defined between SC-007 and SC-008 (`spec.md:446`); FR-022 between FR-007a and FR-008 (`spec.md:265`); FR-019, FR-020 and FR-021 between FR-013 and FR-014. All are AR#1 additions appended where they were topically relevant rather than numerically. Harmless in itself, but FR-023's two-gate table reads out of sequence against the criteria list, which is the one place a reader checks completeness by scanning. | RECORDED. |
| 21 | LOW | **`spec.md:5` Status is still `Draft`** after an adversarial review, a five-question clarification session, a plan, a quickstart, and a second adversarial review. | RECORDED. |

| 22 | HIGH | **Alert NUMBER was the identity in the one comparison that spans remediation.** Swept per the coordinator's propagation, and deliberately swept beyond the success-criteria block, because the sibling that limited its sweep to SC-nnn passed itself and was wrong. Three sites keyed on numbers. SC-005's second clause said "no previously open Python alert transitions to `fixed`"; `plan.md` A2 said "Snapshot the 5 currently open Python alerts by alert NUMBER"; `quickstart.md:31-35` said the check is "only checkable against a pre-change list of alert NUMBERS". Numbers are not stable identities: closing an alert and rewriting the line spawns a fresh number at the same location, so a number-keyed diff reports a loss that did not happen. Two further sites had the same defect latent in a place the narrow sweep would have missed, both spanning the triage window in which "fix now" dispositions actively renumber alerts: US3's **Independent Test** ("every alert in the baseline has exactly one disposition") and **FR-013**, neither of which stated a baseline membership key. A number-keyed baseline decays precisely as the window does its job. | FIXED at all five sites. Identity restated as the (rule identifier, file path) pair in SC-005, FR-013, US3's Independent Test, `plan.md` A2, and the `quickstart.md` A2 query, which now emits a sorted `rule@path` key. Numbers retained as a lookup convenience only. Per the coordinator's Fact 3 correction, the alerts API exposes nothing finer than `path` plus line and column offsets under `most_recent_instance.location`, so rule plus path is the strongest identity mechanically available and no site demands more. |
| 23 | HIGH | **Three runbook checks rendered a read failure as a PASS.** Checked after the coordinator flagged the class. This feature has no `gh api --arg` misuse (verified against `gh api --help` on this machine: zero occurrences of `--arg`; every query uses `--jq`), but it has the more dangerous half of the defect independently. Three checks have EMPTY or ZERO as their PASS value: B1's "zero `Extracted file` lines under `/tests/`", B1's `Extracted file` count, and Phase C's FR-004a resolution-warning grep whose silence means "no warnings", which is the good news this feature's own D-3 says must be measured rather than assumed. All three read from a file produced by `gh run view --log`. A failed fetch leaves an empty file and all three report the passing value. On a security-coverage feature, a fetch failure silently certifying "no test files extracted, no resolution warnings" is the worst available failure direction. | FIXED. Explicit exit-code plus non-empty guards added after both `gh run view --log` redirections, a total-line sanity print, a `PIPESTATUS[0]` note distinguishing "genuinely zero" from "first grep matched nothing", and an explicit `grep rc=` echo on the FR-004a check separating rc 1 (no warnings) from rc 2 (file unreadable). The A2 query gained a read-failure guard for the same reason: an empty alert list would otherwise read as a clean repository. |
| 24 | MEDIUM | **Two citations into sibling features went stale under this review.** `spec.md:43` (F20) cited `specs/001-oauth-provider-taint/quickstart.md:267` as evidence that "TD-024 is already claimed by sibling features", and the Q2 collision note cited that line plus `specs/001-oauth-provider-taint/spec.md:481` and two others. Verified against the current worktree: the sibling's `quickstart.md` no longer contains `TD-024` at all, and its surviving mention has moved to `spec.md:524` where it reads "NOT reserved to this feature". Both citations now point at text saying the opposite of what they were cited for. | FIXED. Line-number citations to sibling artifacts removed rather than re-pinned, since they will drift again. Both sites now state the settled cross-feature rule directly: TD identifiers allocate at MERGE time in merge order, no feature pre-reserves one, and `TD-024` is the arithmetic successor to `TD-023` rather than anyone's claim. |

**Counts**: 2 CRITICAL, 9 HIGH, 8 MEDIUM, 5 LOW. Total 24.

### Checks that came back clean

Recorded because a reviewer reporting only hits is not distinguishable from a reviewer who did not
look.

- **Nothing in any artifact caps, budgets, or thresholds a repo-wide alert count, and nothing
  reads a rise as a regression.** Swept across success criteria, all three Independent Test lines,
  every acceptance scenario including Given and When clauses, and the whole document for
  "primary outcome measure" phrasing. Zero hits. The only three occurrences of "regression" say
  explicitly that a rise is NOT one (`spec.md:16`, FR-014, and acceptance scenario 1.4), and the
  only numeric floor, SC-005's "at least 9 results", is a per-analysis results count on the Python
  leg, not a repo-wide alert count, and is a floor whose reasoning AR#1 already recorded. This
  feature's position is the one the owner directive asks for and it is held consistently.
- **The Q4 evidence base was EXECUTED, not read.** Every claim SC-009 and SC-010 now depend on was
  re-derived by running this feature's own runbook commands: `gh run view 30581930915 --log --job
  91004036909` returns rc 0 and 287,655 bytes over 2,125 lines; the extractor invocation carrying
  `--filter exclude:tests/**/*` is at line 1480 exactly as cited; there are exactly 152
  `Extracted file` lines, the first at line 1487; exactly 0 of them are under `/tests/` with
  `PIPESTATUS[0]` 0, confirming the guard distinguishes a real zero from an empty read; and the
  coverage summary "scanned 152 out of 154 Python files" is at line 2067. The two `git ls-files`
  denominators also verify: 290 in-scope JavaScript and TypeScript files, 393 Python test files.
  Q4's finding is sound and its evidence is reproducible by the commands as written.
- **No before/after measurement runs through the alerts API.** The probe capture at
  `quickstart.md` reads per-analysis SARIF via `analyses/{id}` with
  `Accept: application/sarif+json`, and the inline comment already gives the correct reason. A2
  and E2 are two captures taken at two moments, not one retroactive comparison of two analyses of
  one reference, so they are valid. Finding 8 is a population-mismatch defect, not an API-validity
  defect.
- **No artifact proposes an `npm install` inside the analysis job.** D-3, FR-004a, FR-004b, A4 and
  the supply-chain edge case are mutually consistent, and the reason given is the right one.
- **No success criterion treats a rising alert count as failure.** FR-014, SC-004, acceptance
  scenario 1.4, and the `quickstart.md` reminders all state the opposite explicitly. Finding 9 was
  that `plan.md` failed to SAY it, not that it contradicted it.
- **The `frontend/tests` asymmetry is a deliberate, argued decision**, at `spec.md:808-816`, with a
  stated reason (resolving it needs the unprobed rule change FR-008 bars) and a disposition. Not an
  accident. Finding 14 is downstream tasking, not the decision itself.
- **`plan.md:59` no longer carries the false registry claim.** It reads "CORRECTED at Clarification
  Q2" and cites the real path. Verified against the filesystem: `docs/reference/TECH_DEBT_REGISTRY.md`
  exists, 25479 bytes, highest identifier `TD-023`. The campaign brief's concern is resolved.
- **`plan.md` line 21 is `## Technical Context`**, a real heading. No banned term anywhere in this
  feature directory, and no em-dash.
- **No CodeQL-gates-nothing contradiction.** FR-015, SC-006, the Position section and the Out of
  Scope carding are consistent with the four required contexts, and nothing in any artifact claims
  or plans a new gate.

### GATE

**GATE: 0 CRITICAL, 0 HIGH remaining.**

Both CRITICALs and all nine HIGHs are fixed in the artifacts. Eight MEDIUM and five LOW findings
are recorded, of which findings 10, 11 and 24 were fixed opportunistically as single-line
corrections. Findings 12, 13 and 14 form one cluster inside `spec.md`'s User Story 2 block and
should be fixed in a single pass before implementation.
