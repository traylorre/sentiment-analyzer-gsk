# Tasks: CodeQL Coverage Expansion

**Input**: Design documents from `/specs/001-codeql-coverage/`
**Prerequisites**: `spec.md` (FR-001..FR-023, SC-001..SC-013, Adversarial Review #1, Clarifications Q1-Q5),
`plan.md` (Design Decisions D-1..D-7, Execution Sequence A-F, Adversarial Review #2),
`quickstart.md` (operator runbook, Phases A-F), `checklists/requirements.md`.
No `research.md`, no `data-model.md`, no `contracts/` (deliberately not created, `plan.md` "Deliberately not created").

**Organization**: Phases below map 1:1 onto `plan.md`'s Execution Sequence and `quickstart.md`'s
runbook phases, with one added Phase 0 for preconditions and the artifact corrections AR#2 recorded
as "fix before implementation". Story labels: US1 = customer/admin dashboard code is analyzed at all,
US2 = the scan config says what it does, US3 = the new alerts have somewhere to go.

**Tests**: No unit, contract, or integration tests are owed. No runtime code changes (`plan.md`
Technical Context "Testing"). Every acceptance instrument in this feature is an API read, a job-log
read, or a committed record.

**Two gates, not one (FR-023)**. Phases 0 through D plus E1-E3 close the MERGE gate. Phase F closes
the CLOSE-OUT gate. The feature status stays OPEN between them. Do not mark this file complete when
the pull request merges.

**A rising open alert count is the expected outcome (FR-014, SC-004, owner directive at `spec.md`
Context).** No task below sets a ceiling on the alert count, and no task treats a rise as failure. If
you find yourself writing one, you have misread the feature.

**Arms 1 and 2 of the FR-009b probe are ANSWERED and MUST NOT be run.** No task below dispatches
them. The only permitted configuration mutation before Phase C is the OPTIONAL B2 control arm.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency between them)
- Every verification task states its exact command and its exact pass condition
- Paths are repository-relative

---

## Phase 0: Preconditions and artifact corrections (blocks everything)

- [ ] **T001** Pin the feature context for every subsequent shell. Do NOT run
  `.specify/scripts/bash/create-new-feature.sh`.

  ```bash
  export SPECIFY_FEATURE=001-codeql-coverage
  export REPO=traylorre/sentiment-analyzer-gsk
  export BR=001-codeql-coverage
  export WF=pr-checks.yml

  # Get onto the branch. Measured at AR#3: HEAD was `main`, the local `001-codeql-coverage` branch
  # existed but carried ZERO unique commits (`git rev-list --count main..001-codeql-coverage` = 0),
  # and this feature's five artifacts were UNTRACKED. The previous wording asserted HEAD was already
  # on the branch and told the operator to "stop" otherwise, without supplying the step that gets
  # there. Creating the branch is idempotent-safe either way.
  git rev-parse --verify "$BR" >/dev/null 2>&1 && git switch "$BR" || git switch -c "$BR"
  git rev-parse --abbrev-ref HEAD
  ```

  **Pass condition**: `git rev-parse --abbrev-ref HEAD` prints exactly `001-codeql-coverage`, and
  `echo "$SPECIFY_FEATURE"` prints exactly `001-codeql-coverage`. If HEAD is not on the feature
  branch, stop: every mutation in Phases B and C must land on that branch (FR-010a).

- [ ] **T002** Confirm the feature branch exists on `origin` BEFORE any dispatch is attempted.
  `gh workflow run --ref` resolves the ref server-side, so a branch that exists only locally makes
  A1 fail for a reason that has nothing to do with dispatch permission, which is exactly the
  misreading FR-009c would then record.

  ```bash
  git ls-remote --exit-code --heads origin "$BR"; echo "ls-remote rc=$?"

  # The artifacts must be TRACKED before anything is pushed. `git commit -am` at T016 and T022
  # stages modifications to tracked files ONLY, so untracked files never enter the diff and T030's
  # pass condition 2 (which REQUIRES specs/001-codeql-coverage/ in the diff) could never be met.
  git ls-files specs/001-codeql-coverage/ | wc -l                  # measured at AR#3: 0
  git add specs/001-codeql-coverage/
  git commit -S -m "docs(001): codeql coverage spec, plan, quickstart, tasks"
  git ls-files specs/001-codeql-coverage/ | wc -l                  # must now be > 0

  git push -u origin "$BR"; echo "push rc=$?"
  git ls-remote --exit-code --heads origin "$BR"; echo "ls-remote rc=$?"
  ```

  **Pass condition**: the FINAL `ls-remote rc=0` with one ref line printed, AND
  `git ls-files specs/001-codeql-coverage/` returns a non-zero count, AND
  `git rev-parse --abbrev-ref HEAD` is still `001-codeql-coverage`. **Never run
  `git push -u origin HEAD` while HEAD is `main`**: that pushes `main`, creates no feature ref, and
  leaves T007 failing for the same reason a second time. Do NOT record A1 as NOT RUNNABLE on the
  strength of a dispatch failure taken while the ref did not exist.
  **All three legs of this were measured at AR#3 and all three were open**: `ls-remote` returned
  `rc=2`, the local branch was an exact ancestor of `main` with no unique commits, and
  `git ls-files specs/001-codeql-coverage/` returned `0`. Committing the artifacts is a prerequisite
  of T030, not a courtesy, and nothing else in this file does it.

- [ ] **T003** [P] Correct `specs/001-codeql-coverage/spec.md`. This is the AR#2 finding 12 + 13 + 14
  cluster, which AR#2 explicitly deferred with "should be fixed in a single pass before
  implementation", plus the two spec-side LOW findings. All edits are inside this feature's directory.
  1. **AR#2 finding 12**: three passages still tell the pre-Q4 story and argue against the file's own
     fact table. Rewrite (a) the User Story 2 body, currently "may be dead as a result ... At most one
     of those three things is true. The engineer cannot tell which ... because the behaviour has never
     been probed"; (b) acceptance scenario 2.1, currently opening "Given the contradiction is
     unproven"; (c) the first Edge Case, currently "the two readings of F3 remain indistinguishable".
     All three must read consistently with F3 as amended at Q4: the path exclusion is applied at
     extraction time, the query filter is INERT, the line-13 comment is FALSE.
  2. **AR#2 finding 13**: User Story 2's Independent Test cites "FR-007 through FR-009". FR-007 and
     FR-007a are the `frontend/tests` scope decision, not the probe. Correct to "FR-008 through
     FR-010a".
  3. **AR#2 finding 19**: F3 cites `.github/codeql/codeql-config.yml` "lines 19 to 30". The file is
     29 lines. Correct to "lines 19 to 20 and 23 to 29", which is what Q4 already cites correctly.
  4. **AR#2 finding 17**: the newly-analyzed surface is measured at 47,298 lines. Replace every
     "about 48,000" with "about 47,300" so one measured number has one rendering.
  5. **AR#2 finding 21**: `spec.md` Status is still `Draft` after two adversarial reviews, a
     clarification session, a plan and a quickstart. Set it to the repository's convention for a
     planned feature.

  **Pass condition**: `grep -n 'never been probed\|contradiction is unproven\|remain indistinguishable\|FR-007 through FR-009\|lines 19 to 30\|about 48,000' specs/001-codeql-coverage/spec.md`
  returns nothing (`rc=1`). Confirm `rc=1` explicitly with `echo "rc=$?"`; a `rc=2` means the file
  was unreadable, not that it is clean.

- [ ] **T004** [P] Correct `specs/001-codeql-coverage/plan.md`. Different file from T003, so the two
  run in parallel.
  1. **AR#2 finding 11, now stale in the other direction**: the Documentation tree comment describes
     `spec.md` as "897 lines". Re-measure with `wc -l` and write the measured value, naming both
     appendices. The count moves every time the spec is edited, so make the comment state the
     appendices rather than lean on the number.
  2. **AR#2 finding 17**: Technical Context Constitution Check §3 row says "about 0 to about 48,000".
     Make it 47,300 to match F10 and the Scale/Scope paragraph.
  3. **AR#2 finding 14, partly fixed**: D-4 still tasks the implementer with the FR-007a asymmetry as
     open work ("is argued or carded in the evidence log"). Q4 already wrote the argument in full.
     Retarget D-4 to say the rationale is TRANSCRIBED from Q4, not re-derived, so a second argument
     that disagrees with the first cannot be produced.
  4. **AR#2 finding 18 is itself WRONG and must not be applied.** It claims the Playwright warning
     block is at `pr-checks.yml:389-393` and that D-7's citation of 390-394 is "off by one at both
     ends". Verified on the working tree: line 389 is a bare `#`, the warning paragraph is exactly
     lines 390 to 394, line 395 is the `# ====` rule and 396 opens `playwright-e2e:`. D-7's citation
     is correct as authored. Record the refutation next to D-7 so the next reader does not "fix" a
     correct citation.
  5. **Constitution Check §8 row** currently reads "`make validate` before push. **PASS**". `make
     validate` cannot pass on this tree: `scripts/check-banned-terms.sh` exits 1 on pre-existing
     matches from other features' directories. Replace the claim with the substituted gate defined in
     T005 so the row is true rather than aspirational.

  **Pass conditions**:
  1. `grep -n 'about 48,000\|is argued or carded' specs/001-codeql-coverage/plan.md` returns nothing
     (`rc=1`, confirmed with `echo "rc=$?"`; `rc=2` means the file was unreadable).
  2. The D-7 block still cites `pr-checks.yml:390-394`, checked in the D-7 block ONLY:

     ```bash
     sed -n '/^### D-7\|^- \*\*D-7/,/^- \*\*D-8\|^## /p' specs/001-codeql-coverage/plan.md \
       | grep -c '390-394'                      # must be at least 1
     sed -n '/^### D-7\|^- \*\*D-7/,/^- \*\*D-8\|^## /p' specs/001-codeql-coverage/plan.md \
       | grep -c '389-393\|389-394'             # must be 0
     ```

  **The previous pass condition's guard against this was inert.** It grepped for `389-394`, a string
  that appears nowhere in `plan.md` before or after the fix (verified by execution at AR#3: the only
  hits for that grep were from the other two alternatives, at lines 59, 136, 398 and 401). AR#2
  finding 18's wrong number is `389-393`, and it legitimately appears at `plan.md:402` as append-only
  review HISTORY, which is why the check must be scoped to the D-7 block rather than run file-wide.
  As authored, an implementer who "corrected" D-7 to `389-393` would have passed.

- [ ] **T004a** [P] Correct `specs/001-codeql-coverage/quickstart.md`. Different file from T003 and
  T004, so all three run in parallel. **This task exists because the Cross-Artifact Analysis closed
  section E with "`quickstart.md` should be updated to match section E before anyone executes from
  it" and then gave that sentence no step.** `quickstart.md` is the OPERATOR RUNBOOK: it is the one
  artifact in this feature whose commands get pasted into a shell verbatim, and it carries eleven
  recorded mechanical defects that this file fixed only in its own copies. An operator running the
  runbook never reaches the corrected forms.

  Apply E1 through E11 from section E, which is to say:
  1. **E10 / D9, the one that matters.** Four unpaginated `analyses` reads: lines 105-106 and
     150-151 (`per_page=10`), 215-216 and 230-231 (`per_page=30`). Replace all four with
     `--paginate --slurp > file` plus a separate `jq '[.[][] | ...]'`, per T016, T023, T033 and T037.
  2. **E3 / D2.** Lines 36-38 and 222-227 use `--paginate` with an AGGREGATING `--jq`. Replace with
     `--paginate --slurp` and a separate `jq`.
  3. **E2 / D1.** The guards at lines 84 and 162 print STOP and continue; the guard at line 39 ends
     in a bare `false`. Give all three `|| { echo ...; exit 1; }`.
  4. **E4 / D3.** Line 226-227's `js/` plus `py/` partition is not exhaustive. Add `other` and
     `partition_check`, per T034.
  5. **E5 / D4.** Phase C tier 1 must print `first-grep rc=${PIPESTATUS[0]}` for both counts.
  6. **E6 / D7.** Line 234 reads `.contexts` only. Print `.checks[].context` and the two length
     floors as well, per T038.
  7. **E1 / C1.** Phase A1 dispatches before any ref check. Add the T002 `git ls-remote` gate ahead
     of it, and the T001 branch switch ahead of that.
  8. **E7 / C3, E8 / C4, E9, E11.** Deferral 2 becomes a step rather than prose; the Phase D registry
     read is re-taken at write time; the FR-007a
     skeleton bullet is retargeted at Q4 as a transcription; the Phase E `run view --json jobs` read
     gets a guard and a leg-present assertion.
  9. **Two skeleton defects, found at AR#3 and not previously recorded.** The "Record skeletons"
     section holds THREE skeletons (`## Probe record`, `## Pre-merge verification`,
     `## Baseline record`), while T006 instructs the operator to build the evidence log "from the
     four skeletons" and its pass condition demands at least four `^## ` headers. Add a fourth,
     `## Close-out record`, carrying the SC-008 count field, the SC-013 outcome field and the §9
     entries line, and remove those three lines from the baseline skeleton where they currently sit.
     Also correct the section preamble, which says "Both live in ..." over three skeletons and omits
     `enforcement-recommendation.md` (T041) entirely.
  10. Line 253's probe skeleton states "Tracked `.py` files: 544 total, 393 under `tests/`".
      Re-measured at AR#3: both numbers are CORRECT. Leave them.

  **Pass conditions**:
  1. `grep -c 'per_page=10\|per_page=30' specs/001-codeql-coverage/quickstart.md` prints `0`.
  2. `grep -c '\-\-paginate' specs/001-codeql-coverage/quickstart.md` equals
     `grep -c '\-\-slurp' specs/001-codeql-coverage/quickstart.md`, and neither is `0`.
  3. `grep -c 'STOP\."; }$' specs/001-codeql-coverage/quickstart.md` prints `0` (no guard ends
     without `exit 1`), confirmed with `echo "rc=$?"`; `rc=1` is the clean result and `rc=2` means
     the file was unreadable.
  4. `grep -c '^## ' ` over the "Record skeletons" region shows four skeleton headers.
  5. `bash scripts/check-banned-terms.sh 2>&1 | grep -c 'specs/001-codeql-coverage'` still prints
     `0` (the edits introduce no banned term).

- [ ] **T005** Define the pre-push gate this feature actually uses, and record it in `plan.md`'s
  Constitution Check §8 row (the edit itself is T004 item 5).

  ```bash
  bash scripts/check-banned-terms.sh > /tmp/banned-before.txt 2>&1; echo "baseline rc=$?"
  grep -c 'specs/001-codeql-coverage' /tmp/banned-before.txt; echo "rc=${PIPESTATUS[0]}"
  ```

  **Pass condition**: the second command prints `0` with `rc=1` from `grep -c` (zero matches) and the
  file `/tmp/banned-before.txt` is non-empty. Zero matches under this feature's own directory is the
  only banned-terms result this feature owns. A whole-tree `rc=1` from the script is EXPECTED and is
  not this feature's defect. **Do not make any task in this file depend on `make validate` exiting 0.**

- [ ] **T006** Create `specs/001-codeql-coverage/evidence-log.md` with FOUR section headers present
  and every field left blank: `## Probe record` (FR-010), `## Pre-merge verification`,
  `## Baseline record` (FR-013 / FR-019 / FR-020 / FR-021), `## Close-out record` (SC-013).
  **`quickstart.md` supplies only THREE.** Measured at AR#3: its "Record skeletons" section contains
  `## Probe record`, `## Pre-merge verification` and `## Baseline record`, and the close-out fields
  are folded into the baseline skeleton rather than given a heading. An operator copying the runbook
  faithfully produces three `^## ` headers and fails this task's own pass condition with nothing left
  to copy. T004a adds the fourth skeleton to `quickstart.md`; until it lands, write the
  `## Close-out record` header here by hand, carrying the SC-008 count field, the SC-013 outcome
  field and the §9 registry-entries line. Apply the two skeleton corrections below at creation time
  so they are never filled in wrong:
  - The pre-merge SC-003 field offers **PROVEN (tier 1|2|3)** or **UNPROVEN** only. There is no `no`
    value (SC-003 anti-false-negative rule).
  - The close-out record carries **"Undispositioned count at window close, BEFORE the FR-016b default
    is applied: N"** as a numeric field, recorded even when N is zero (SC-008).

  **Pass condition**: `grep -c '^## ' specs/001-codeql-coverage/evidence-log.md` prints at least `4`,
  and `grep -c 'BEFORE the FR-016b default' specs/001-codeql-coverage/evidence-log.md` prints `1`.

**Checkpoint**: Phase 0 complete. No repository file outside `specs/001-codeql-coverage/` has been
touched. Nothing has been dispatched.

---

## Phase A: Pre-flight (US1, US2, US3)

- [ ] **T007** [P] [US2] **A1: establish whether manual dispatch on the feature branch is available.**
  Note this is not a passive permission check: it starts a real Python-only run. That is harmless
  (the matrix is still `['python']` and the config is unmutated) but it is a CI state change, so
  record the run id.

  ```bash
  gh workflow run "$WF" --repo "$REPO" --ref "$BR"; echo "dispatch rc=$?"
  sleep 15
  gh run list --repo "$REPO" --workflow "$WF" --branch "$BR" --limit 3 \
    --json databaseId,event,status,createdAt --jq '.[]'
  ```

  **Pass condition**: `dispatch rc=0` AND the listing shows at least one run with
  `"event":"workflow_dispatch"` created within the last few minutes. Record `DISPATCH AVAILABLE: yes`
  plus the run id in the probe record.
  **If `dispatch rc` is non-zero**: first re-check T002 (a missing remote ref produces the same
  failure and is not a permission problem). Only if the ref exists, record `DISPATCH AVAILABLE: no`
  and apply **FR-009c**: this is an inconclusive probe, NOT a licence to change any rule (FR-008
  still holds) and NOT a reason to defer User Story 2. Concretely: B1 (T011-T014) runs regardless
  because it needs no dispatch, B2 (T015-T016) is recorded NOT RUNNABLE and resolves to RETAIN by
  FR-009b's default, B3 (T017) runs, and SC-002, SC-003 and SC-007 move from pre-merge (T024-T028) to
  the post-merge `refs/heads/main` run.

- [ ] **T008** [P] [US1] **A2: snapshot the currently open Python alerts BEFORE anything changes**,
  keyed on the `(rule identifier, file path)` PAIR. This is the only artifact that makes SC-005's
  second clause checkable later. **Identity is never the alert number**: closing an alert and
  rewriting the line spawns a fresh number at the same location, so a number-keyed diff reports a
  loss that did not happen. The alerts API exposes nothing finer than `path` plus line and column
  offsets under `most_recent_instance.location`, so `rule@path` is the strongest identity
  mechanically available and SC-005 asks for no more.

  ```bash
  gh api "repos/$REPO/code-scanning/alerts?ref=refs/heads/main&state=open&per_page=100" \
    --paginate --slurp > /tmp/a2-raw.json
  rc=$?
  [ "$rc" -eq 0 ] && [ -s /tmp/a2-raw.json ] \
    || { echo "A2 API READ FAILED (rc=$rc). An empty list would read as a clean repository. STOP."; exit 1; }
  jq '[.[][] | {key: "\(.rule.id)@\(.most_recent_instance.location.path)",
                number, sev: .rule.security_severity_level}] | sort_by(.key)' \
    /tmp/a2-raw.json | tee /tmp/a2-prechange.json | jq 'length'
  ```

  **Pass condition**: the final `jq 'length'` prints a number greater than 0 (F7 predicts `5`), and
  `/tmp/a2-prechange.json` is non-empty. A printed `0` after a successful read is a real result and
  must be recorded as such, but it contradicts F7 and requires re-verification before proceeding.
  **Why `--slurp` and not `--jq` directly**: `gh api --paginate --jq` applies the filter per page and
  concatenates, so an aggregating filter emits one result object per page rather than one for the
  whole set. This feature EXPECTS the post-change set to grow past one page, so the pattern is fixed
  here rather than at E2 where it would first bite.
  **Produces**: the pre-change open-alert list, pasted into the evidence log keyed on `rule@path`,
  with numbers retained only as a lookup convenience.

- [ ] **T009** [US3] **A3, Deferral 2 (the 10-working-day triage window, spec.md Clarifications Q5).
  This one is LOAD-BEARING and it has a deadline.** Ask the owner to confirm 10 working days or name
  a different number, and ask it **before T036 (E2)**. FR-021 writes the computed calendar close-out
  date into the baseline record at CAPTURE time and FR-016a permits exactly ONE extension, so an
  answer arriving after E2 spends that single extension on an authoring correction instead of on
  alert volume, which is the precise scarcity FR-016a exists to protect.

  **Owner**: Admin Role (Project Owner: @traylorre), `CONTRIBUTING.md:64`.
  **Trigger**: raised at Phase A, must be answered or declared unanswered at T038.
  **Pass condition**: the evidence log records one of exactly two states, with a date:
  `WINDOW: 10 working days, CONFIRMED by owner on YYYY-MM-DD` or
  `WINDOW: 10 working days, ASSUMED, Deferral 2 unanswered at capture`. A blank field fails this task.
  **Fallback if unanswered at T038**: record ASSUMED, say so in the baseline record, and treat any
  later owner change as the FR-016a extension it is, spending the single permitted extension.

- [ ] **T010** [US3] **A3, Deferral 1 (constitution §9 cites the stale registry path, spec.md
  Clarifications Q2).** Not blocking, and not this feature's to fix. Route it into
  `enforcement-recommendation.md` (T043) so it reaches the same named decider under that document's
  decision-by date, rather than expiring inside a clarifications appendix.

  Question to carry verbatim: constitution §9 cites `docs/TECH_DEBT_REGISTRY.md` at
  `.specify/memory/constitution.md` lines 527, 569 and 584, but the registry has lived at
  `docs/reference/TECH_DEBT_REGISTRY.md` since `f8db8d2` (PR #668). Amend §9 to the real path, or
  move the file back?

  **Owner**: same Admin Role, as the F2 recommendation's named decider.
  **Trigger**: carried at Phase A, discharged when T043 writes it into the recommendation.
  **Pass condition**: the evidence log records `DEFERRAL 1: routed to enforcement-recommendation.md
  (F2), not blocking`, and T043's checklist includes it.

**Checkpoint**: A1 outcome recorded, the pre-change Python alert list captured on `rule@path`, both
deferrals have a named owner, a trigger and a destination.

---

## Phase B: Config resolution (US2). Config only, matrix untouched, Python-only.

**AMENDED at Clarification Q4. Arms 1 and 2 of the superseded three-arm probe MUST NOT be run.**
They are ANSWERED from extraction-level evidence already present in a `refs/heads/main` full-tree
job log, and running them would mutate the shared config to re-derive a settled fact, which FR-008
and FR-009b both bar. One arm survives and it is OPTIONAL. Every step in this phase is admissible
under **FR-009** because its source is a branch reference, never a pull request reference.

- [ ] **T011** [US2] **B1 read, with the guard first.** Several checks in T012 have ZERO as their
  PASS value, so a failed fetch produces an empty file and every one of them renders as a pass. On a
  security-coverage feature, silently certifying "no test files extracted" is the worst available
  failure direction. Assert the log is real before reading it.

  ```bash
  gh run view 30581930915 --repo "$REPO" --log --job 91004036909 > /tmp/py-main.log
  rc=$?
  [ "$rc" -eq 0 ] && [ -s /tmp/py-main.log ] \
    || { echo "LOG FETCH FAILED (rc=$rc). Every zero below is meaningless. STOP."; exit 1; }
  wc -l /tmp/py-main.log
  ```

  **Pass condition**: `rc=0` and `wc -l` prints a line count in the low thousands (AR#2 re-executed
  this and measured 2,125 lines / 287,655 bytes). A count under 100 means the fetch degraded and
  T012 must not run. Note the `|| { ...; exit 1; }`: the guard must STOP, not merely print. An
  advisory guard that only echoes leaves every downstream zero believable.

- [ ] **T012** [US2] **B1 transcribe the Q4 extraction evidence into the probe record.** No dispatch,
  no mutation. **This task alone satisfies SC-009 and SC-010** on the path FR-009b permits.

  ```bash
  grep -n 'filter exclude' /tmp/py-main.log            # expect a hit at line 1480
  grep -c 'Extracted file' /tmp/py-main.log            # expect 152
  grep 'Extracted file' /tmp/py-main.log | grep -c '/tests/'; echo "first-grep rc=${PIPESTATUS[0]}"
  grep -n 'CodeQL scanned' /tmp/py-main.log            # expect line 2067
  git ls-files '*.py' | grep -c '^tests/'              # expect 393
  ```

  **Pass conditions, all five**:
  1. `filter exclude` matches at line **1480** and the matched text contains
     `--filter exclude:tests/**/*`.
  2. `Extracted file` count is **152**. A count of 0 means the guard in T011 failed.
  3. The `/tests/` count is **0 AND `first-grep rc=0`**. A `0` count with `first-grep rc=1` means the
     FIRST grep matched nothing, that is, the log is wrong or empty, NOT that no test file was
     extracted. Both values must be checked; the count alone is not a check.
  4. `CodeQL scanned` matches at line **2067** and reads "scanned 152 out of 154 Python files".
  5. The tracked Python test file count is **393**, none of which appear in (2).

  **Produces**, in the probe record: run `30581930915`, job `91004036909`, `refs/heads/main`, the
  three log line numbers above, the verbatim extractor invocation and coverage summary lines, and the
  conclusion: of F3's three claims exactly the first is true. `paths-ignore` performs the exclusion at
  EXTRACTION time; the `tests/**` query filter is INERT; the line-13 comment is FALSE. Arms 1 and 2
  are ANSWERED and were not run.

- [ ] **T013** [US2] **FR-006 record**: review the shared config for rules written with only Python in
  mind that will begin applying to the JavaScript/TypeScript leg, and record each one's disposition.
  Per D-4 there are exactly two rules and they resolve in opposite directions:
  - `query-filters` names `py/incomplete-url-substring-sanitization`, a Python rule identifier that
    cannot match any JavaScript or TypeScript rule. **INERT for the new leg.**
  - `paths-ignore: tests/**/*` is genuinely language-neutral and **DOES apply to the new leg**. Being
    root-anchored it reaches `tests/load/api-load-test.js` and does NOT reach `frontend/tests`.

  ```bash
  grep -cE '^(paths-ignore|query-filters|paths|queries|disable-default-queries|packs):' \
    .github/codeql/codeql-config.yml
  grep -nE '^[a-z-]+:' .github/codeql/codeql-config.yml
  ```

  **Pass condition**: the first count prints exactly **`2`** (`paths-ignore` and `query-filters`), the
  enumeration shows exactly three top-level keys (`name`, `paths-ignore`, `query-filters`), and the
  evidence log's FR-006 record names both rules with a disposition each. A record naming only one
  rule fails. **If the count is greater than 2, a rule block exists that this task has not reviewed
  against the new leg, and FR-006 is not satisfied until it is.**
  **The previous pass condition had no target value and could not be passed or failed.** Executed at
  AR#3: `grep -cE '^\s*-|^[a-z-]+:' .github/codeql/codeql-config.yml` prints **`6`** (lines 15, 19,
  20, 23, 26, 29), because the pattern also catches `name:` and every list item. Six was offered as
  confirmation that the file "carries exactly the two rule blocks", with no stated expectation, so
  an operator had no value to compare against.

- [ ] **T014** [US2] **FR-007 and FR-007a decision, TRANSCRIBED from Clarification Q4, not
  re-derived.** Q4 already wrote the argument in full; producing a second argument invites one that
  disagrees with the first.
  - **FR-007 decision**: `frontend/tests` is IN SCOPE for scanning (A2). 101 files, about 19,900
    lines.
  - **FR-007a asymmetry, argued**: the asymmetry is larger than glob anchoring alone suggests. The
    Python side is an extraction-level exclusion removing 393 files from the database entirely. The
    `frontend/tests` side is 101 files matching no exclusion pattern at all. Narrowing or widening
    either side requires editing a rule in the shared config, which FR-008 bars until the surviving
    B2 control question is answered. The asymmetry is therefore **preserved deliberately for this
    feature's duration, because resolving it would require exactly the unprobed rule change FR-008
    exists to prevent**. The symmetry question stays carded, already in Out of Scope, with no tech
    debt registry entry per the Q2 triage.

  **Pass condition**: the evidence log's FR-007/FR-007a section contains a reason, not just a
  decision, and the reason names FR-008. `grep -c 'FR-008' ` over that section returns at least 1.
  Leaving the asymmetry undiscussed fails FR-007a, because an undiscussed asymmetry is
  indistinguishable from the glob accident that produced it.

- [ ] **T015** [US2] **B2 decision gate: run the OPTIONAL control arm, or do not.** Decide and record
  before touching anything. The arm has exactly one purpose: to decide whether to DELETE the inert
  query filter as dead or RETAIN it against a future narrowing of the path exclusion. It is the
  FR-009a positive control, and per FR-009a a zero result declares the probe INCONCLUSIVE
  immediately, with no further arms.

  **Pass condition**: the probe record's B2 Status field reads exactly one of `RUN`, `NOT RUN`, or
  `NOT RUNNABLE (FR-009c)`.
  **If NOT RUN or NOT RUNNABLE**: skip T016. FR-009b's stated default governs and the query filter is
  **RETAINED unchanged**, because deleting a rule without evidence is precisely what FR-008 forbids.
  Neither outcome blocks the feature and neither fails SC-009 or SC-010, which T012 already satisfies.
  **Under no circumstances run arm 1 or arm 2.** They are ANSWERED (FR-009b) and running them mutates
  the shared config to re-derive a settled fact.

- [ ] **T016** [US2] **B2 control arm, CONDITIONAL on T015 reading `RUN`. MUTATES the config, on the
  feature branch only (FR-010a).** Remove BOTH `paths-ignore: tests/**/*` and the
  `py/incomplete-url-substring-sanitization` query filter, commit on `$BR`, dispatch a full-tree
  Python-only run.

  ```bash
  # MUTATES .github/codeql/codeql-config.yml: remove both rules
  git commit -S -am "probe(001): codeql config control arm"
  git push origin "$BR"
  gh workflow run "$WF" --repo "$REPO" --ref "$BR"

  gh api "repos/$REPO/code-scanning/analyses?ref=refs/heads/$BR&per_page=100" \
    --paginate --slurp > /tmp/b2-analyses.json
  rc=$?
  [ "$rc" -eq 0 ] && [ -s /tmp/b2-analyses.json ] \
    || { echo "ANALYSES READ FAILED (rc=$rc). An empty list is not 'the arm produced nothing'. STOP."; exit 1; }
  jq '[.[][] | {id, category, created_at, results_count, commit_sha}] | sort_by(.created_at) | reverse' \
    /tmp/b2-analyses.json

  ID=<analysis id for this arm, matched by commit_sha to the probe commit>
  gh api "repos/$REPO/code-scanning/analyses/$ID" \
    -H "Accept: application/sarif+json" > "/tmp/arm-$ID.sarif"
  rc=$?
  [ "$rc" -eq 0 ] && [ -s "/tmp/arm-$ID.sarif" ] \
    || { echo "SARIF FETCH FAILED (rc=$rc). A zero result below would be a read failure. STOP."; exit 1; }
  jq '[.runs[].results[] | .locations[0].physicalLocation.artifactLocation.uri as $p
       | select($p | startswith("tests/"))
       | {rule: .ruleId, path: $p}]
      | {count: length, rules: [.[].rule] | unique, paths: [.[].path] | unique}' \
    "/tmp/arm-$ID.sarif"
  ```

  **Pass condition**: the SARIF file is non-empty AND the `jq` emits a `count` value. The count is the
  result, not the pass condition: any value including 0 is a valid outcome.
  **Why SARIF and not the alerts endpoint**: an alert carries only `most_recent_instance`, which a
  later run on the SAME reference overwrites, so an alerts-API read cannot separate one run of a
  reference from another. Per-analysis SARIF is the only mechanism that can. This constraint applies
  to comparing two analyses of one reference; it does NOT apply to T008 and T036, which are two
  captures taken at two different MOMENTS, and those are valid as written.
  **Outcome routing**: `count = 0` resolves the SAME way as NOT RUN. The filter is RETAINED unchanged
  (FR-009b, FR-008). The rule may simply no longer fire: per F4, six of the eight historical alerts
  for it are `fixed`. Only a positive count licenses DELETE.
  **Produces**: the arm's analysis identifier, its verbatim config as run, its commit sha, and its
  result count, rules and paths under `tests/` (FR-010).

- [ ] **T017** [US2] **B3, MUTATES `.github/codeql/codeql-config.yml`. Revert anything T016 changed,
  then apply the FR-011 resolution.** If T016 did not run there is nothing to revert.
  - The comment at line 13, "All other security rules apply to tests", is FALSE per Q4 and is
    **removed**. Lines 6 to 12 and line 22 ("But we still want to scan tests for other issues") carry
    the same false implication and must be brought into agreement in the same edit.
  - The stated intent is made explicit: `tests/**/*` is excluded at EXTRACTION time, so no Python test
    file enters the database and no query filter scoped to `tests/**` can have any effect.
  - **No rule is added or deleted** except on the strength of a positive T016 result (FR-008,
    FR-009b's retain-unchanged default).

  **Pass conditions**:
  1. `git diff --stat .github/codeql/codeql-config.yml` shows that file and no other.
  2. `grep -n 'All other security rules apply to tests' .github/codeql/codeql-config.yml` returns
     nothing (`rc=1`, confirmed with `echo "rc=$?"`).
  3. `grep -c 'paths-ignore' .github/codeql/codeql-config.yml` prints `1` and
     `grep -c 'py/incomplete-url-substring-sanitization' .github/codeql/codeql-config.yml` prints `1`,
     UNLESS T016 returned a positive count and DELETE was chosen and recorded.
  4. `git log --oneline origin/main..HEAD -- .github/codeql/codeql-config.yml` shows no commit whose
     message contains `control arm` surviving as the file's final state (FR-010a: no probe arm reaches
     `main`).
  **Also binds**: FR-012. This edit MUST NOT reduce Python analysis coverage below the F7 baseline for
  any rule other than the single deliberately filtered one. FR-012 is VERIFIED later, at T039, against
  the post-merge `refs/heads/main` Python analysis; it is asserted here and checked there.

**Checkpoint**: the config's comments and rules agree, the probe record is complete, no arm mutation
survives, and no rule changed without evidence.

---

## Phase C: Matrix change (US1)

- [ ] **T018** [US1] **FR-003 scope ceiling, stated in this feature's artifacts rather than
  discovered from the first result set.** Confirm and record the ceiling before the leg runs.

  ```bash
  git ls-files '*.js' '*.jsx' '*.ts' '*.tsx' '*.mjs' '*.cjs' | wc -l            # tracked total
  git ls-files '*.js' '*.jsx' '*.ts' '*.tsx' '*.mjs' '*.cjs' | grep -vcE '^tests/'  # in scope
  git ls-files '*.js' '*.jsx' '*.ts' '*.tsx' '*.mjs' '*.cjs' | grep -cE '^frontend/src/'
  git ls-files '*.js' '*.jsx' '*.ts' '*.tsx' '*.mjs' '*.cjs' | grep -cE '^frontend/tests/'
  git ls-files '*.js' '*.jsx' '*.ts' '*.tsx' '*.mjs' '*.cjs' | grep -cE '^src/dashboard/'
  ```

  **Pass condition**: tracked total `291`, in scope `290`, `frontend/src` `173`, `frontend/tests`
  `101`, `src/dashboard` `6`, leaving 10 configuration and contract-stub files. If any number differs,
  record the measured value and the commit it was measured at rather than the expected one, and carry
  the delta into T026's tier 3 denominator. The scope ceiling is "every JavaScript and TypeScript file
  outside the root-anchored `tests/**/*` exclusion", which is WIDER than the two dashboards: it also
  reaches root and `frontend/` configuration files and four contract stub files under `specs/`, which
  are specification artifacts that never ship (F15).

- [ ] **T019** [US1] **C1: add `javascript-typescript` to the matrix.** Edit
  `.github/workflows/pr-checks.yml`, job `codeql` (`name: Analyze`, block opens at line 282), matrix
  at line 294 at `c010178`. Anchor by content, not by line number.

  ```yaml
      strategy:
        fail-fast: false
        matrix:
          language: ['python', 'javascript-typescript']
  ```

  **Pass conditions**:
  1. `grep -n "language: \['python', 'javascript-typescript'\]" .github/workflows/pr-checks.yml`
     returns exactly one line.
  2. `grep -n 'fail-fast: false' .github/workflows/pr-checks.yml` still shows the line immediately
     above the matrix (FR-002: one leg failing must not cancel or suppress the other).
  3. `grep -n 'queries: security-extended' .github/workflows/pr-checks.yml` is unchanged and shared by
     both legs (FR-005: adding a language must not silently ship a weaker suite for it).
  4. `grep -n 'category: "/language:${{matrix.language}}"' .github/workflows/pr-checks.yml` is
     unchanged (D-6: per-language categories are what let SC-001 and SC-005 be checked independently;
     a shared category collapses them into one number).
  5. **One value, not two.** `javascript` and `typescript` must NOT appear as separate matrix entries.
     TypeScript is analyzed by the JavaScript extractor with TypeScript enabled by default (D-1,
     FR-001, F9).

- [ ] **T020** [US1] **C1: add the FR-022 matrix-context warning comment** to the `codeql` job header,
  modeled on the existing `playwright-e2e` warning at `.github/workflows/pr-checks.yml:390-394`
  (verified: line 389 is a bare `#`, the warning paragraph is 390 to 394, 395 is the `# ====` rule).
  Use the D-7 text from `plan.md`.

  **Pass conditions**:
  1. `grep -n 'PER MATRIX VALUE' .github/workflows/pr-checks.yml` returns exactly one line, and it
     sits above `codeql:` (line 282 region), not above any other job.
  2. **SC-012 second clause**: the workflow contains no OTHER job whose status context is generated
     per matrix value and which lacks such a warning. Verify by enumerating matrix jobs:
     `grep -n 'matrix:' .github/workflows/pr-checks.yml` and confirming each hit belongs to a job that
     either carries a warning or reports a single non-matrix context. Record the enumeration in the
     evidence log; an unenumerated "none found" does not satisfy the clause.

- [ ] **T021** [US1] **FR-004, FR-004a and FR-004b decisions, recorded as explicit decisions rather
  than left as unexamined defaults.** No file changes; this is a record.
  - **FR-004 (build)**: NO build step. `autobuild` stays unconditional and is a no-op for JavaScript
    and TypeScript (D-2). If the first run contradicts F9, state the prerequisite explicitly and
    provision it; do not work around it.
  - **FR-004a (dependency install)**: **NO install**, with BOTH reasons recorded. First, per F17 the
    analysis job holds `security-events: write` and is triggered by `pull_request` on a PUBLIC
    repository, so an install step there would execute contributor-authored package lifecycle scripts
    inside a job holding write access to the security-events surface. Fork runs get a downgraded
    read-only token; branch pushes by any account with write access do not. Second, the feature is
    scoped to first-party findings. **The COST is recorded, not assumed away**: without installed
    dependencies, type resolution and library modelling degrade, which weakens taint tracking through
    framework boundaries in exactly the first-party code this feature exists to cover, and the owner
    directive names taint analysis specifically. T027 measures that cost from the job log.
  - **FR-004b (how it may be revisited)**: any future install MUST NOT be placed in a job that both
    holds `security-events: write` and is reachable from an untrusted reference. T043 carries this
    constraint into the enforcement recommendation.

  ```bash
  # Scope the grep to the codeql job. Anchor by content, not by the literal line numbers.
  START=$(grep -n '^  codeql:' .github/workflows/pr-checks.yml | cut -d: -f1)
  END=$(awk -v s="$START" 'NR>s && /^  [a-z][a-z0-9_-]*:/ {print NR-1; exit}' .github/workflows/pr-checks.yml)
  echo "codeql job = lines $START to $END"
  [ -n "$START" ] && [ -n "$END" ] || { echo "JOB BLOCK NOT LOCATED. STOP."; exit 1; }
  sed -n "${START},${END}p" .github/workflows/pr-checks.yml \
    | grep -c 'npm install\|npm ci\|yarn install\|pnpm install'
  ```

  **Pass condition**: `START` and `END` are both non-empty, and the scoped count prints `0`, and the
  evidence log records all three decisions with their reasons. A recorded decision that omits the
  COST fails FR-004a.
  **The unscoped form was wrong and would have failed on a correct tree.** Executed at AR#3:
  `grep -c 'npm install\|npm ci\|...' .github/workflows/pr-checks.yml` prints **`2`**, not `0`. Both
  hits are `cd frontend && npm ci` at lines 424 and 511, in the frontend-test and Playwright jobs,
  neither of which is the analysis job and neither of which FR-004a says anything about. The prose
  scoped the check to the `codeql` block; the command scanned the whole file. A check that fails on
  a correct tree is worse than no check, because it teaches the operator to wave the next one
  through. (Measured at AR#3, the `codeql` job spans lines 282 to 313 and contains no install step.)

- [ ] **T022** [US1] **C2: commit, push, and dispatch a full-tree run on
  `refs/heads/001-codeql-coverage`.**

  ```bash
  git commit -S -am "feat(001): add javascript-typescript to the CodeQL matrix"
  git push origin "$BR"
  gh workflow run "$WF" --repo "$REPO" --ref "$BR"; echo "dispatch rc=$?"
  RUN=$(gh run list --repo "$REPO" --workflow "$WF" --branch "$BR" --limit 1 \
    --json databaseId --jq '.[0].databaseId')
  echo "RUN=$RUN"; [ -n "$RUN" ] || { echo "RUN EMPTY. STOP."; exit 1; }
  gh run watch "$RUN" --repo "$REPO"
  ```

  **Pass condition**: `dispatch rc=0`, `RUN` is non-empty, and `gh run watch` reports the run
  concluded. The `Analyze (javascript-typescript)` job must appear in the run. Its conclusion may be
  `success` or `failure`: a failing new leg is a result to record, not a reason to skip T023 to T028.
  **If T007 recorded dispatch unavailable**: skip T022 to T028 and take SC-002, SC-003 and SC-007 from
  the post-merge `refs/heads/main` run at Phase E instead, recording that substitution in the evidence
  log.

- [ ] **T023** [US1] **SC-002: the JavaScript/TypeScript analysis reports a results count.**

  ```bash
  gh api "repos/$REPO/code-scanning/analyses?ref=refs/heads/$BR&per_page=100" \
    --paginate --slurp > /tmp/c2-analyses.json
  rc=$?
  [ "$rc" -eq 0 ] && [ -s /tmp/c2-analyses.json ] \
    || { echo "ANALYSES READ FAILED (rc=$rc). STOP: an absent entry below would be a read failure."; exit 1; }
  jq '{total: ([.[][]] | length),
       jsts: [.[][] | select(.category | test("javascript")) | {id, category, created_at, results_count}]}' \
    /tmp/c2-analyses.json
  ```

  **Pass condition**: `rc=0`, `total` is greater than 0, AND the `jsts` array holds at least one
  object carrying a `results_count` key. **Any value including 0 satisfies SC-002; an ABSENT analysis
  does not.** Record the value and the analysis id in the pre-merge verification section.
  **`--paginate` is load-bearing, not cosmetic.** This branch accumulates one analysis per language
  per dispatch, and by this point it has seen the T007 dispatch, possibly the T016 arm, and this run.
  A default 30-item page truncates newest-first, so an unpaginated read can return a page holding no
  JavaScript/TypeScript entry at all and the operator would record "an ABSENT analysis" against a
  leg that ran fine. **A truncated read must never be recorded as an SC-002 failure**, which is why
  the guard exits rather than letting the `jsts` array render as empty.

- [ ] **T024** [US1] **Fetch the JavaScript/TypeScript job log, with the guard first.** T025 and T027
  both treat SILENCE as good news, so a failed fetch would report a clean bill of health.

  ```bash
  JOB=$(gh run view "$RUN" --repo "$REPO" --json jobs \
    --jq '.jobs[] | select(.name=="Analyze (javascript-typescript)") | .databaseId')
  echo "JOB=$JOB"; [ -n "$JOB" ] || { echo "JOB ID EMPTY. STOP."; exit 1; }
  gh run view "$RUN" --repo "$REPO" --log --job "$JOB" > /tmp/jsleg.log
  rc=$?
  [ "$rc" -eq 0 ] && [ -s /tmp/jsleg.log ] \
    || { echo "JS LEG LOG FETCH FAILED (rc=$rc). Silence below is a read failure, not a result. STOP."; exit 1; }
  wc -l /tmp/jsleg.log
  ```

  **Pass condition**: `JOB` non-empty, `rc=0`, `/tmp/jsleg.log` non-empty, and `wc -l` prints a count
  in the hundreds or thousands. Record the byte and line count in the evidence log so a later reader
  can tell a real read from a degraded one.

- [ ] **T025** [US1] **SC-003: evidence that source files under BOTH `frontend/` and `src/dashboard/`
  entered the database.** The three-tier order is load-bearing (Clarification Q3).

  ```bash
  # TIER 1 (primary). Paths in these lines are ABSOLUTE runner paths appearing MID-LINE, after the
  # "<job>\t<step>\t<timestamp>" prefix gh prepends. A line-anchored '^frontend/' returns 0
  # UNCONDITIONALLY and is a guaranteed false negative. Match unanchored substrings.
  grep 'Extracted file' /tmp/jsleg.log | grep -c '/frontend/';     echo "t1a first-grep rc=${PIPESTATUS[0]}"
  grep 'Extracted file' /tmp/jsleg.log | grep -c '/src/dashboard/'; echo "t1b first-grep rc=${PIPESTATUS[0]}"
  grep -c 'Extracted file' /tmp/jsleg.log                          # per-file lines present at all?

  # TIER 2 (only if tier 1 emitted NO per-file lines AT ALL for either directory).
  grep -nE 'Calling |extractor|--filter' /tmp/jsleg.log | head -20

  # TIER 3 (corroboration only).
  grep -n 'CodeQL scanned' /tmp/jsleg.log
  ```

  **Pass conditions**:
  - **Tier 1 PROVEN**: both counts greater than 0 with `first-grep rc=0` on both. Record
    `frontend/ PROVEN (tier 1)` and `src/dashboard/ PROVEN (tier 1)`.
  - **Tier 2**, used only when `grep -c 'Extracted file'` prints 0: per-file logging is
    extractor-specific and the JavaScript extractor exposes no logging-verbosity option, so zero
    per-file lines is a logging-VERBOSITY outcome, not a coverage outcome. Fall back to the extractor
    invocation line, which prints the scan root and the active `--filter exclude:` set. Both
    directories being under the scan root and matching no exclusion establishes scope. Record
    `PROVEN (tier 2)`.
  - **Tier 3**, corroboration only: reconcile "CodeQL scanned N out of M JavaScript/TypeScript files"
    against the 290 in-scope files from T018. **Tier 3 can never by itself prove the admin dashboard**:
    its tolerance is wider than `src/dashboard`'s 6 files (the Python leg's own count was 154 against
    151 tracked files). It corroborates and ranks last.
  - **Anti-false-negative rule, mandatory**: absence of evidence at any tier is recorded as
    `SC-003 UNPROVEN` and carried into the evidence log as an OPEN ITEM. It MUST NOT be recorded as
    "the admin dashboard was not extracted". **There is no `no` value.** UNPROVEN does not fail the
    MERGE gate; asserting a coverage gap that was never observed would be worse than admitting the log
    did not say.

- [ ] **T026** [US1] **FR-004a measurement: type-resolution and module-resolution warnings from the
  job log.** EMPTY output here means "no resolution warnings", which is the GOOD outcome, so it is
  only believable because T024's guard passed.

  ```bash
  grep -inE 'could not resolve|module resolution|type resolution|no such module|cannot find module' /tmp/jsleg.log
  echo "grep rc=$? (0 = warnings found, 1 = genuinely no warnings, 2 = file unreadable)"
  ```

  **Pass condition**: `rc` is 0 or 1, and the evidence log records WHICH it was together with the
  matched lines when `rc=0`. `rc=2` fails this task: re-run T024. Recording "none found" without
  recording the return code fails FR-004a, because the whole point is that a future revisit of the
  no-install decision is evidence-backed rather than a re-argument.

- [ ] **T027** [US1] **SC-007: wall clock, leg bound and total bound.**

  ```bash
  gh run view "$RUN" --repo "$REPO" --json jobs > /tmp/c2-jobs.json
  rc=$?
  [ "$rc" -eq 0 ] && [ -s /tmp/c2-jobs.json ] \
    || { echo "JOBS READ FAILED (rc=$rc). STOP: a missing leg below is a read failure, not a fast leg."; exit 1; }
  jq '.jobs[] | {name, started_at, completed_at}' /tmp/c2-jobs.json
  jq '[.jobs[] | select(.name | test("javascript-typescript"))] | length' /tmp/c2-jobs.json
  gh run view "$RUN" --repo "$REPO" --json createdAt,updatedAt,conclusion --jq '.'
  ```

  **Pass conditions**: the second `jq` prints `1` (the leg is present in the jobs list at all), and
  the `Analyze (javascript-typescript)` leg completes **within 8 minutes** AND
  total workflow wall clock stays **within 2 minutes of the pre-change 5 to 7 minutes**. If the leg
  exceeds 8 minutes, report BOTH bounds and **the total bound governs**. Record all three numbers
  (leg, total, pre-change total) in the evidence log; a pass recorded without the numbers is not
  checkable.

- [ ] **T028** [US1] **FR-019 pre-registration: record this run's analysis identifier as EXCLUDED from
  baseline capture.** The baseline must come from an analysis run under the EXACT configuration that
  lands on `main`; baselining a pre-merge branch analysis would baseline a configuration that never
  shipped.

  **Pass condition**: the pre-merge verification section names the T023 analysis id followed literally
  by `<- EXCLUDED from baseline capture per FR-019`, and T036's baseline record names a DIFFERENT
  analysis id. If the two ids match, the baseline is invalid and T036 must be redone.

- [ ] **T029** [US1] **FR-018 evidence-source audit.** Sweep every claim of coverage made so far and
  confirm none of it rests on a pull request check.

  ```bash
  grep -nE 'refs/pull|pull request check|PR check|checks passed' specs/001-codeql-coverage/evidence-log.md
  echo "rc=$?"
  ```

  **Pass condition**: `rc=1` (no matches), OR every match is an explicit statement that pull request
  evidence is BARRED. A green pull request check is never evidence the repository is clean, only that
  the changed lines are (F5, F6). Pull request analyses are diff-informed and routinely report zero
  results; that is correct behaviour, not a broken gate.

**Checkpoint**: the matrix change is committed on the branch, the leg has run on a branch reference,
and SC-002, SC-003, SC-007 and the FR-004a measurement are recorded with their evidence.

---

## Phase D: Merge and the merge-time half of the §9 obligation

- [ ] **T030** [US1] **D1: open the pull request.** Run the pre-push checks, substituting the T005
  gate for `make validate` (which cannot pass on this tree for reasons that predate this feature).

  ```bash
  # --paginate is MANDATORY here. The default page size is 30 and this repository's all-states
  # code-scanning corpus is 137 items, with the open alerts sitting past the end of page one.
  # Without --paginate this exact query returns ZERO open alerts and renders truncation as CLEAN.
  gh api "repos/$REPO/code-scanning/alerts?state=open&per_page=100" --paginate --slurp \
    > /tmp/prepush-alerts.json
  rc=$?
  [ "$rc" -eq 0 ] && [ -s /tmp/prepush-alerts.json ] \
    || { echo "PRE-PUSH ALERT READ FAILED (rc=$rc). An empty list is NOT a clean repository. STOP."; exit 1; }
  jq '{open_total: ([.[][]] | length),
       alerts: [.[][] | {rule: .rule.id, path: .most_recent_instance.location.path}]}' \
    /tmp/prepush-alerts.json
  bash scripts/check-banned-terms.sh 2>&1 | grep -c 'specs/001-codeql-coverage'; echo "rc=${PIPESTATUS[0]}"
  git diff --stat origin/main..HEAD
  ```

  **Pass conditions**:
  1. The banned-terms count under this feature's directory is `0`.
  2. `git diff --stat` shows exactly: `.github/workflows/pr-checks.yml`,
     `.github/codeql/codeql-config.yml`, and files under `specs/001-codeql-coverage/`. Any other path
     in the diff is scope creep and must be removed or explained.
  3. **FR-015**: the diff touches no branch-protection or ruleset configuration. This feature adds no
     merge gate.
  4. `open_total` is greater than 0 (F7 predicts 5 at this point). **A printed `0` here is a read
     failure until proven otherwise, not a clean repository.** The listing is recorded for reference
     and **is NOT a gate**: this feature does not fix the 5 open Python alerts (Out of Scope) and a
     rise in the count is expected, not blocking. Note this number now has TWO independent ways to be
     wrong, and neither may render as success: a truncated read makes it too low, and this feature's
     own leg makes it legitimately higher. Record the read's completeness (paginated, guarded)
     alongside the number so the two can be told apart later.

- [ ] **T031** [US1] **D1: merge, and leave the feature status OPEN.** The MERGE gate per FR-023 is
  SC-001, SC-002, SC-003, SC-005, SC-006, SC-007, SC-009, SC-010, SC-012. SC-001 and SC-005 are
  satisfied by the first `refs/heads/main` run immediately after merge, which is why the gate reads
  "at merge, plus the first `refs/heads/main` run".

  **Pass condition**: the pull request is merged AND `specs/001-codeql-coverage/evidence-log.md`
  carries the literal line `FEATURE STATUS: OPEN (FR-023, MERGE gate passed, CLOSE-OUT gate pending)`.
  **Closing the feature here is the failure mode FR-016b names, reached by a different route.**

- [ ] **T032** [P] [US3] **D2: discharge the MERGE-TIME half of the constitution §9 obligation.**
  Clarification Q2 withdrew the §9 deviation by disproving the "registry does not exist" premise,
  which converted a justified gap into a live requirement. The Q2 triage names three genuine debt
  items. **Two are UNCONDITIONAL and are owed AT MERGE, not at close-out**; the third is conditional
  and belongs to T044.

  ```bash
  grep -oE 'TD-[0-9]{3}' docs/reference/TECH_DEBT_REGISTRY.md | sort -u | tail -1
  echo "rc=${PIPESTATUS[0]}"
  ```

  **Identifier allocation**: **AT MERGE TIME, in merge order, against the registry's then-highest
  value. Never pre-reserved.** `TD-024` is the arithmetic successor to `TD-023` and is not this
  feature's claim; the settled cross-feature rule, shared by all four features in this campaign, is
  merge-time allocation. Pre-reserving is what created the collision this rule exists to prevent. Read
  the highest value at the moment you write, not at the moment you read this file.

  Write two sequential entries in `docs/reference/TECH_DEBT_REGISTRY.md`, per constitution §9(a):
  1. **npm ecosystem absent from `.github/dependabot.yml`** while 82 npm advisories are open (F18).
     §9 trigger: "dependency issues requiring future attention".
  2. **The §10 local-SAST gap this feature widens**: `make sast` runs Bandit and Semgrep over `src/`
     only, so after this lands CodeQL covers `frontend/` and no local pre-push tier does. §9 trigger:
     "known limitations".

  **Pass conditions**: `grep -c 'TD-' docs/reference/TECH_DEBT_REGISTRY.md` increased by exactly 2
  against its pre-task value, and the two new identifiers are sequential from the value read above.
  **Skipping this makes the Constitution Check §9 row false at merge**, which is the same defect
  AR#1 finding 1 caught elsewhere.

  **§9(b) is NOT discharged by this task, and the evidence log must say so rather than claim §9
  complete.** §9(b) asks for a `tech-debt`-labelled GitHub issue per entry. The label does not exist
  in this repository (13 labels: `bug`, `documentation`, `duplicate`, `enhancement`,
  `good first issue`, `help wanted`, `invalid`, `question`, `wontfix`, `dependencies`, `python`,
  `github-actions`, `terraform`), and the owner has directed that it **NOT** be created and that no
  issues be raised against it, with the whole question audited once at the end of the campaign. So:
  do not run `gh label create`, do not run `gh issue create`, and do not substitute another label.
  Record the §9(b) half as outstanding, naming the owner directive as the reason. The same applies to
  T044's conditional third entry, which runs long after this one.

---

## Phase E: Baseline (US3), after merge only

- [ ] **T033** [US1] **E1: capture the FIRST `refs/heads/main` JavaScript/TypeScript analysis produced
  by the post-merge push.** This identifier, and no other, starts the A1 triage clock.

  ```bash
  gh api "repos/$REPO/code-scanning/analyses?ref=refs/heads/main&per_page=30" --paginate --slurp \
    > /tmp/e1-analyses.json
  rc=$?
  [ "$rc" -eq 0 ] && [ -s /tmp/e1-analyses.json ] || { echo "E1 READ FAILED (rc=$rc). STOP."; exit 1; }
  N=$(jq '[.[][] | select(.category != null and (.category | test("javascript")))] | length' \
        /tmp/e1-analyses.json)
  echo "jsts_analyses=$N"
  [ "$N" -gt 0 ] \
    || { echo "ZERO javascript-typescript analyses on refs/heads/main. SC-001 NOT met. STOP."; exit 1; }
  jq '[.[][] | select(.category != null and (.category | test("javascript")))]
      | sort_by(.created_at) | .[0]
      | {id, category, created_at, results_count, commit_sha}' /tmp/e1-analyses.json
  ```

  **Pass condition** (**SC-001**): `N` is greater than 0, AND the printed object's `id` is non-null,
  AND its `category` names JavaScript/TypeScript, AND its `created_at` is AFTER the merge commit.
  **The count floor is the check; "a non-null object is printed" is NOT.** Verified by execution at
  AR#3 against the live 948-analysis `refs/heads/main` corpus, every entry of which is
  `/language:python`: `[...] | sort_by(.created_at) | .[0] | {id, category, ...}` over an EMPTY
  selection prints `{"id":null,"category":null,...}`, whose `type` is `"object"` and whose
  `. == null` is `false`. An operator applying the previous wording would have recorded SC-001 as
  satisfied with no JavaScript/TypeScript analysis in existence, and written `null` into the FR-021
  baseline record as the identifier that starts the triage clock. `null` is also why `.category` is
  null-guarded before `test()`: `null | test(...)` aborts the whole filter rather than skipping a row.
  `sort_by` then `.[0]` takes the EARLIEST such analysis, which is what A1 requires; the API's default
  ordering is newest first, so dropping the sort would pick the wrong one and start the clock late.
  **`--paginate` is what makes the sort mean anything.** Measured at AR#3: `refs/heads/main` carries
  948 analyses. The unpaginated `per_page=30` form used by `quickstart.md` E1 yields an oldest-of-page
  of `2026-07-25`, against a true oldest of `2025-11-20`, an eight-month error in the value that
  becomes a deadline.

- [ ] **T034** [US3] **E2: capture the baseline alert set, filtered to the SAME population A2
  captured, and partitioned exhaustively.**

  ```bash
  gh api "repos/$REPO/code-scanning/alerts?ref=refs/heads/main&state=open&per_page=100" \
    --paginate --slurp > /tmp/e2-raw.json
  rc=$?
  [ "$rc" -eq 0 ] && [ -s /tmp/e2-raw.json ] || { echo "E2 READ FAILED (rc=$rc). STOP."; exit 1; }
  jq '[.[][] | {number, rule: .rule.id, sev: .rule.security_severity_level,
                path: .most_recent_instance.location.path,
                key: "\(.rule.id)@\(.most_recent_instance.location.path)"}]
      | {total_open: length,
         jsts:   [.[] | select(.rule | startswith("js/"))],
         python: [.[] | select(.rule | startswith("py/"))],
         other:  [.[] | select((.rule | startswith("js/")) or (.rule | startswith("py/")) | not)]}
      | . + {partition_check: (.total_open == ((.jsts|length)+(.python|length)+(.other|length)))}' \
    /tmp/e2-raw.json | tee /tmp/e2-baseline.json | jq '{total_open, jsts: (.jsts|length), python: (.python|length), other: (.other|length), partition_check}'
  ```

  **Pass conditions**:
  1. `rc=0` and `/tmp/e2-raw.json` non-empty. An empty alert list would otherwise read as a clean
     repository.
  2. `partition_check` is `true`. **The `other` bucket exists deliberately**: the Python leg also
     analyzes GitHub Actions workflow files ("152 out of 154 Python files and 5 out of 5 GitHub
     Actions files"), so a two-bucket `js/` plus `py/` partition is NOT exhaustive and would silently
     drop `actions/`-prefixed alerts from both the baseline and the delta. A non-empty `other` bucket
     is a result to record, not an error.
  3. `state=open` is present. Without it the query returns all states, including the 15 dismissed and
     117 fixed of F7, and the SC-004 delta at T035 would compare an all-states population against
     A2's open-only one, reporting a large FICTITIOUS increase inside a feature whose central claim is
     that a real increase is the expected outcome. A fake increase inside that framing is uniquely
     hard to catch.
  4. `--slurp` is present, for the pagination reason given at T008. This feature EXPECTS the set to
     grow past one page.

  **Produces** (FR-013, FR-019, FR-020): the baseline record, listing count, rule identifiers,
  severities and file paths, **with membership keyed on the `(rule identifier, file path)` pair**.
  Alert numbers MAY be recorded as a lookup convenience but MUST NOT be the identity: "fix now"
  dispositions land INSIDE the triage window and remediating an alert spawns a fresh number at the
  rewritten line, so a number-keyed baseline would show members vanishing and non-members appearing
  purely as an artifact of the fixes the window exists to produce. The record MUST name the T033
  analysis identifier it was taken from, and that identifier MUST differ from T028's (FR-019).

- [ ] **T035** [US3] **E2: partition into path classes BEFORE triage begins (FR-020), and publish the
  SC-004 delta with FR-014 framing.**

  Partition the `jsts` bucket into at minimum three classes:

  | Path class | Members |
  |---|---|
  | Product code | `frontend/src`, `src/dashboard` |
  | Test code | `frontend/tests` |
  | Non-shipping artifacts | build configuration files, contract stubs under `specs/` (F15) |

  A single recorded disposition MAY cover an entire path class where the rule identifier AND the
  reason are identical across every alert in that class, and that bulk disposition counts as
  satisfying FR-016 for each alert it covers. This exists so a baseline dominated by test-only or
  stub-only findings does not make FR-016 arithmetically unmeetable, without weakening the requirement
  that nothing is left undispositioned. The volume at risk is real, not remote: about 19,900 lines of
  `frontend/tests` against 22,295 lines of the `frontend/src` it exercises.

  **SC-004 delta**: record `open before: 5 | open after: N | delta: N-5`.
  **Pass condition** (**SC-004**): the delta is PUBLISHED in the baseline record with all three
  numbers. **Acceptance does NOT depend on the delta being zero or negative. An increase satisfies
  this criterion.**
  **FR-014 framing, mandatory wording**: the delta is recorded as *newly revealed pre-existing
  exposure*, never as a regression this feature introduced. The alerts were always there; until now
  nothing was looking. A record that describes the rise as a regression fails FR-014 regardless of its
  arithmetic.
  **Also record**: the FR-004a resolution-warning note carried forward from T026.

- [ ] **T036** [US3] **E2: write the FR-021 fields at CAPTURE TIME.** A duration with no start date is
  not a deadline; writing the calendar date into the record at capture time is what converts it into
  one.

  Three fields, all mandatory, all at capture:
  1. **Named accountable role for triage**: `Admin Role (Project Owner: @traylorre)`, cited to
     `CONTRIBUTING.md:64`, whose listed responsibilities already include "Respond to security
     incidents" (`CONTRIBUTING.md:74`). **Record it with the citation**, not as a bare handle, so a
     later reader can check it against a source.
  2. **The source analysis identifier** the baseline was taken from (T033), so FR-019's exclusion is
     checkable.
  3. **The close-out date in ISO 8601 (`YYYY-MM-DD`)**, computed as 10 working days from that
     analysis's timestamp, per constitution Amendment 1.5's date rule.

  **Pass condition**: all three fields non-blank, plus the T009 window field reading exactly
  `CONFIRMED by owner on YYYY-MM-DD` or `ASSUMED (Deferral 2 unanswered at capture)`. **This is
  Deferral 2's landing point.** If it is still unanswered, record ASSUMED, say so, and treat any later
  owner change as the FR-016a extension it is, spending the single permitted extension on an authoring
  correction. That is the cost T009 exists to avoid.

- [ ] **T037** [US1] **E3: SC-005, Python coverage does not REGRESS.** Two clauses, both required.

  ```bash
  jq '[.[][] | select(.category | test("python"))] | sort_by(.created_at) | reverse | .[0]
      | {id, created_at, results_count}' /tmp/e1-analyses.json          # clause 1

  # clause 2. Keys are counted WITH MULTIPLICITY. Bare array subtraction is not usable here.
  jq -s 'def tally: group_by(.key) | map({key: .[0].key, n: length}) | INDEX(.key) | map_values(.n);
         (.[0] | tally) as $b
         | (.[1].jsts + .[1].python + .[1].other | tally) as $a
         | {shrunk:     [$b | to_entries[] | select(.value > ($a[.key] // 0))
                         | {key: .key, before: .value, after: ($a[.key] // 0)}],
            disappeared:[$b | to_entries[] | select($a[.key] == null) | .key],
            appeared:   [$a | to_entries[] | select($b[.key] == null) | .key]}' \
     /tmp/a2-prechange.json /tmp/e2-baseline.json
  ```

  **Pass conditions**:
  1. The newest `refs/heads/main` Python analysis reports **at least 9** `results_count`. This is
     deliberately a FLOOR and not an equality. If the config work widened Python scope, the count
     rises above 9, and an equality test would fail the feature for producing exactly the outcome
     FR-012 protects.
  2. **BOTH `disappeared` AND `shrunk` are empty arrays.** Identity is the `(rule identifier, file
     path)` pair, NEVER the alert number: closing an alert and rewriting the line spawns a fresh
     number at the same location, so a number-keyed comparison reports a spurious loss. `appeared` is
     expected to be non-empty and is not a failure; it is the point of the feature.
     **`shrunk` is not decoration, and the earlier `disappeared`-only form was vacuous on live data.**
     `rule@path` is NOT unique in the current open set. Measured at AR#3 against
     `refs/heads/main`: of the five open alerts, THREE share the single key
     `py/clear-text-logging-sensitive-data@src/lambdas/ingestion/handler.py` (numbers 148, 149, 150).
     jq's array `-` removes EVERY occurrence of each right-hand element, so a key that drops from
     three members to one still subtracts away completely. Demonstrated by execution: deleting alerts
     149 and 150 from the pre-change capture and running the previous clause-2 filter verbatim emits
     `{"disappeared": [], "appeared": []}`, that is, two open high-severity alerts vanish and SC-005
     passes. The multiplicity tally closes it: the same deletion now reports
     `shrunk: [{key: "...ingestion/handler.py", before: 3, after: 1}]`.
  3. Both `jq` invocations exit 0 and print non-null output. A null from clause 1 means the read
     degraded, not that Python coverage vanished.

  **Also verifies FR-012**: the T017 config edit did not reduce Python analysis coverage relative to
  the F7 baseline for any rule other than the single deliberately filtered one.

- [ ] **T038** [US1] **E3: SC-006 and SC-012, no collateral damage to gates or comments.**

  ```bash
  gh api "repos/$REPO/branches/main/protection/required_status_checks" > /tmp/e3-protection.json
  rc=$?
  [ "$rc" -eq 0 ] && [ -s /tmp/e3-protection.json ] \
    || { echo "PROTECTION READ FAILED (rc=$rc). An empty context set is NOT 'no gates changed'. STOP."; exit 1; }
  jq '{contexts: .contexts, checks: [.checks[].context],
       n_contexts: (.contexts | length), n_checks: (.checks | length)}' /tmp/e3-protection.json
  grep -c 'PER MATRIX VALUE' .github/workflows/pr-checks.yml
  grep -n 'matrix:' .github/workflows/pr-checks.yml
  ```

  **Pass conditions**:
  0. `n_contexts` and `n_checks` are both `4` and neither is `null`. A `null` from a dropped or
     renamed API field would otherwise satisfy "no unexpected context" vacuously. This is a single
     object, not a paginated collection, so `--paginate` does not apply; the floor does.
  1. **SC-006**: `rc=0` AND the returned set contains exactly the four contexts from F8:
     `Secrets Scan`, `Lint`, `Run Tests`, `Playwright E2E Tests`, unchanged in NAME and COUNT. Both
     `.contexts` (deprecated but still populated) and `.checks[].context` are printed so a future
     API-shape change is visible rather than silent. Note the change ADDS the context
     `Analyze (javascript-typescript)` and does NOT rename `Analyze (python)` (F16), so nothing that
     branch protection names can have moved.
  2. **SC-012**: the `PER MATRIX VALUE` count is exactly 1, and the enumeration of `matrix:` hits
     confirms no OTHER matrix-context job lacks a warning. Record the enumeration; "none found" without
     the enumeration does not satisfy the clause.

**Checkpoint**: MERGE gate fully evaluated. SC-001, SC-002, SC-003, SC-005, SC-006, SC-007, SC-009,
SC-010 and SC-012 each carry a recorded outcome. The feature status is still OPEN.

---

## Phase F: Close-out (US3), on the recorded close-out date

- [ ] **T039** [US3] **F1: disposition every baseline alert within the window (FR-016, FR-020).** Each
  baseline alert receives **exactly one** of: `fix now`, `carded follow-up`, or `dismissed with a
  recorded reason`. One bulk disposition may cover a whole path class where the rule identifier AND
  the reason are identical across it. The window opens at the timestamp of the T033 analysis and
  closes on the calendar date written at T036.

  **Pass condition**: every `rule@path` key in the T034 `jsts` baseline appears exactly once in the
  disposition table. Verify by key, not by count:

  ```bash
  jq -r '.jsts[].key' /tmp/e2-baseline.json | sort -u > /tmp/f1-expected.txt
  # extract the disposition table's keys into /tmp/f1-actual.txt, then:
  diff /tmp/f1-expected.txt /tmp/f1-actual.txt; echo "rc=$?"
  ```

  `rc=0` means complete. `rc=1` lists exactly the undispositioned set, which is what T042 counts.
  **Note**: a non-blocking enforcement position is a statement about the automated gate, not about
  triage urgency. FR-016 requires disposition inside the window regardless of severity, and `fix now`
  is the expected route for anything at critical or high severity.

- [ ] **T040** [US3] **F1: the FR-016a extension, if used.** The window MAY be extended **exactly
  ONCE**, to a new FIXED calendar date recorded in the baseline record alongside the reason. It MUST
  NOT be extended a second time. An indefinitely extensible window is a deferral wearing a deadline's
  clothes.

  **Pass condition**: the baseline record's extension field reads `used? no` or
  `used? yes, new date YYYY-MM-DD, reason: <text>`, and appears at most once in the file's history.
  **The response to unmanageable volume is never to reduce coverage back down**, which would invert
  the owner directive. FR-020's path-class bulk disposition exists so that volume alone does not force
  an extension. If T009's answer arrived late and consumed this extension, that is recorded as such.

- [ ] **T041** [P] [US3] **F2: write `specs/001-codeql-coverage/enforcement-recommendation.md`**
  (FR-017, FR-017a, SC-011). Different file from T039's evidence log, so the two run in parallel:
  the recommendation is justified by the observed alert VOLUME from T034 and T035, not by T039's
  dispositions.

  Mandatory contents:
  1. A **severity threshold**.
  2. A **path scope**.
  3. A **blocking or non-blocking position**, justified by the observed alert volume.
  4. The **role that decides on it**: Admin Role (Project Owner: @traylorre), `CONTRIBUTING.md:64`.
  5. A **decision-by date** in ISO 8601.
  6. **FR-017a adjacent questions**: the `frontend/tests` symmetry question raised by FR-007a
     (TRANSCRIBED from T014's Q4 argument, not re-argued), and the FR-004b constraint that any future
     dependency install must not sit in a job that both holds `security-events: write` and is
     reachable from an untrusted reference.
  7. The **§10 local-SAST gap** recorded in `plan.md`'s Constitution Check.
  8. **Deferral 1** from T010, verbatim, so it inherits this document's named decider and
     decision-by date.
  9. The carded question of **promoting CodeQL to a required status check**, which is deliberately OUT
     OF SCOPE and is an owner question. This feature adds no merge gate (FR-015) and changes no
     required context (SC-006).

  **Pass condition** (**SC-011**): the file exists inside this feature's directory and
  `grep -cE 'severity threshold|path scope|blocking|decides|decision-by' specs/001-codeql-coverage/enforcement-recommendation.md`
  returns at least 5, with all nine items above individually present. A recommendation with no named
  recipient is a document, not a decision request. It is **carried forward as a follow-up item, not
  applied inside this feature**.

- [ ] **T042** [US3] **F3 step 1: COUNT FIRST.** The order of T042, T043 and T044 is load-bearing and
  was made so at Clarification Q5. **SC-008 is evaluated at window close BEFORE FR-016b's default is
  applied**, because after the default every alert carries a disposition by construction and the
  criterion could never fail, which would make it decorative.

  ```bash
  comm -23 /tmp/f1-expected.txt /tmp/f1-actual.txt | tee /tmp/f3-undispositioned.txt | wc -l
  ```

  **Pass condition** (**SC-008**): the number is written into the close-out record **as a number,
  including when it is zero**, and the undispositioned set itself is recorded VERBATIM.
  `100 percent of baseline JavaScript/TypeScript alerts carry exactly one recorded disposition`
  corresponds to the number being `0`. **This number, and only this number, is what SC-008 is measured
  against.** A close-out record with a blank or absent count fails SC-008 even if every alert happens
  to be dispositioned.

- [ ] **T043** [US3] **F3 step 2: THEN apply the FR-016b default.** Every alert in
  `/tmp/f3-undispositioned.txt` is recorded as `carded follow-up`, so the count never silently drops.

  **Pass condition**: after this task the disposition table covers every baseline key
  (`diff /tmp/f1-expected.txt /tmp/f1-actual.txt` returns `rc=0`), AND the T042 number is still
  recorded unchanged. Applying the default before counting reproduces exactly the vacuity Q5 removed.

- [ ] **T044** [US3] **F3 step 3: THEN record the close-out outcome (SC-013), and discharge the
  CLOSE-OUT half of the §9 obligation if the lapse path fired.**
  - **T042's count is 0** → outcome `COMPLETE`.
  - **T042's count is non-zero** → outcome `FAILED CLOSE-OUT`, recorded as such rather than quietly
    complete, AND one follow-up item is raised carrying the undispositioned set: a sequential entry in
    `docs/reference/TECH_DEBT_REGISTRY.md`, per constitution §9(a). Its §9(b) half is outstanding for
    the reason given at T032: the label is not to be created and no issue is to be raised against it.
    Record it as outstanding. This is the **third and CONDITIONAL** item of the Q2 triage, distinct from the two
    unconditional entries T032 wrote at merge. **Identifier allocated at that moment against the
    registry's then-highest value, never pre-reserved**, exactly as at T032, and the value read at
    T032 will already be stale by now.

  **Pass condition** (**SC-013**): the close-out record carries an outcome of literally `COMPLETE` or
  `FAILED CLOSE-OUT`. A close-out with no recorded outcome does not satisfy this criterion, and
  neither does a feature that was marked complete at merge. When the outcome is `FAILED CLOSE-OUT`,
  the registry carries the new entry. This is the criterion that makes FR-016b observable rather than
  aspirational.

- [ ] **T045** [US3] **FR-023 final sweep: both gates evaluated, and the sweep itself recorded.**

  **Pass conditions**, checked one by one against the evidence log:

  | Gate | Criteria | Every one carries a recorded outcome |
  |---|---|---|
  | MERGE | SC-001, SC-002, SC-003, SC-005, SC-006, SC-007, SC-009, SC-010, SC-012 | T033, T023, T025, T037, T038, T027, T012, T012, T038 |
  | CLOSE-OUT | SC-004, SC-008, SC-011, SC-013 | T035, T042, T041, T044 |

  Then, and only then, change `FEATURE STATUS: OPEN` to the recorded close-out outcome.
  **Do not perform this task at merge.** SC-004, SC-008, SC-011 and SC-013 cannot be satisfied until
  the close-out date, and closing the feature at merge is the exact failure mode FR-023 exists to
  prevent: every criterion that carries enforcement weight would be evaluated after the pull request
  is closed and everyone has stopped looking.

---

## Dependencies

- **T001 → T002 → everything.** T002 in particular gates T007: a missing remote ref and an absent
  dispatch permission produce the same failure and would be recorded as the wrong one.
- **T003 [P] T004 [P] T004a** (three different files), all three → T005 → T006. **T004a is the
  runbook repair and is a hard prerequisite of Phase A**, because Phase A is the first phase an
  operator would drive from `quickstart.md` rather than from this file.
- **T006 → T007, T008** (the evidence log must exist before anything writes to it). T007 and T008 are
  [P] with each other: independent API reads appending to different sections, and the append order
  does not matter.
- **T009, T010** anytime in Phase A. **T009 has a hard deadline at T036** and must be RAISED here, not
  there.
- **T011 → T012 → T013, T014.** The guard strictly precedes every check whose pass value is zero.
- **T012 → T015 → T016 (conditional) → T017.** T012 before T015 is load-bearing: the evidence record
  exists before any arm is considered, and T012 alone is what satisfies SC-009 and SC-010, so no rule
  change ever depends on an arm count.
- **All of Phase B → all of Phase C** (FR-019 and D-5: the probe is Python-only precisely so it cannot
  structurally produce a JavaScript/TypeScript result set to accidentally baseline).
- **T018 → T019 → T020 → T021 → T022** (same file for T019/T020, so not parallel).
- **T022 → T023, T024; T024 → T025, T026** (both read `/tmp/jsleg.log`); **T022 → T027**.
- **T023 → T028** (the id being excluded must first exist).
- **T029** after everything in Phase C that writes evidence.
- **All of Phase C → T030 → T031.** **T032 [P]** with T033: different files, both post-merge.
- **T031 → T033 → T034 → T035 → T036.** T033 before T034 because the baseline record must name the
  analysis id it came from.
- **T008 and T034 → T037** (the clause-2 diff needs both captures).
- **T034, T035 → T039**; **T039 → T042 → T043 → T044**, and that three-step order must not be
  collapsed.
- **T041 [P]** with T039: different files, and the recommendation depends on T034/T035's volume, not
  on T039's dispositions.
- **T044 → T045**, last.

## Parallelizable tasks

7 of 46: **T003**, **T004**, **T004a**, **T007**, **T008**, **T032**, **T041**. The feature is
dominated by a strict evidence ordering, so genuine parallelism is scarce and claiming more would be
false.

## Implementation Strategy

Three sittings, not one, because the calendar is part of the design.

**Sitting 1 (Phases 0, A, B, C, D)**: the whole mechanical change. Two configuration files, one
matrix value, one warning comment, one comment deletion, plus the probe record, the pre-merge
verification and two registry entries. Wall clock is dominated by waiting on dispatched runs, not by
editing.

**Sitting 2 (Phase E)**: immediately after the post-merge push completes, because T033 must take the
FIRST `refs/heads/main` JavaScript/TypeScript analysis and T036 writes the close-out date computed
from its timestamp. Delay here shortens the real triage window without shortening the recorded one.

**Sitting 3 (Phase F)**: on the recorded close-out date. Nothing in this repository can mechanically
enforce that date. There is no automation that fails a build because a disposition is missing, and
that is a real weakness stated rather than papered over. What the design buys instead is that a lapse
is visible and attributable rather than silent: T033 pins the start to a specific analysis identifier,
T036 writes the date into an artifact at capture time, T040 caps extensions at one, T042 to T044 make
a lapse produce a recorded value, and T045 refuses to close the feature at merge.

---

## Requirement coverage

Every functional requirement and every success criterion maps to at least one task. No gaps.

### Functional requirements (33 of 33 covered)

| Requirement | Subject | Tasks |
|---|---|---|
| FR-001 | JavaScript/TypeScript in the matrix, combined identifier | T019 |
| FR-002 | Legs report independently, `fail-fast: false` | T019 (pass condition 2) |
| FR-003 | Scope includes both dashboards; ceiling stated explicitly | T018 |
| FR-004 | No build step required | T021, T022 |
| FR-004a | No dependency install, both reasons AND the cost recorded | T021, T026, T035 |
| FR-004b | Any future install barred from a `security-events: write` job reachable from an untrusted ref | T021, T041 (item 6) |
| FR-005 | Same query suite depth for both legs | T019 (pass condition 3) |
| FR-006 | Python-only config rules reviewed against the new leg | T013 |
| FR-007 | `frontend/tests` treatment is an explicit recorded decision | T014 |
| FR-007a | The asymmetry against excluded Python tests is argued or carded | T014, T041 (item 6) |
| FR-008 | No rule change before an empirical probe | T015, T017 |
| FR-009 | Probe on a branch reference; pull request evidence inadmissible | T012, T016, T029 |
| FR-009a | Positive control before any comparison is meaningful | T015, T016 |
| FR-009b | Arms 1 and 2 ANSWERED and MUST NOT run; surviving arm OPTIONAL; retain-unchanged default | T015, T016 |
| FR-009c | Probe not runnable routes to FR-011 inconclusive, not to a rule change | T007 |
| FR-010 | Probe recorded reproducibly: identifiers, configs, counts, control outcome | T012, T016 |
| FR-010a | Probe mutations confined to the branch, never reach `main` | T016, T017 (pass condition 4) |
| FR-011 | Config ends with comments and rules in agreement | T017 |
| FR-012 | No reduction in Python coverage except the one filtered rule | T017 (asserted), T037 (verified) |
| FR-013 | Baseline record: count, rules, severities, paths, keyed on `(rule, path)` | T034 |
| FR-014 | New alerts are newly revealed pre-existing exposure; a rise is not failure | T035 |
| FR-015 | Same non-blocking enforcement state; no merge gate added | T030 (pass condition 3), T038 |
| FR-016 | Exactly one disposition per baseline alert inside the window | T039 |
| FR-016a | Window extendable exactly ONCE, to a fixed date, with a reason | T040 |
| FR-016b | Lapse behaviour: count, then default, then FAILED CLOSE-OUT, then one follow-up item | T042, T043, T044 |
| FR-017 | Enforcement recommendation as a committed deliverable with a decider and a date | T041 |
| FR-017a | Recommendation also covers the symmetry question and the install constraint | T041 (item 6) |
| FR-018 | Coverage claims evidenced from a branch reference or the alert API, never a pull request check | T029 |
| FR-019 | Baseline from the exact landed configuration; probe analyses excluded by identifier | T028, T034 |
| FR-020 | Path-class partition before triage; bulk disposition permitted per class | T035, T039 |
| FR-021 | Role, source analysis id, and close-out DATE written at capture time | T036 |
| FR-022 | Matrix-context warning comment on the analysis job | T020 |
| FR-023 | Two gates; feature stays open between them | T031, T045 |

### Success criteria (13 of 13 covered)

| Criterion | Measured how | Tasks |
|---|---|---|
| SC-001 | A `refs/heads/main` analyses entry categorised for JavaScript/TypeScript, dated after the change | T033 |
| SC-002 | That analysis reports a `results_count`; any value including 0 passes, absence does not | T023, T034 |
| SC-003 | Three-tier job-log evidence for `frontend/` and `src/dashboard/`, with UNPROVEN permitted | T025 |
| SC-004 | Open alert delta against the pre-change 5, published; an increase satisfies it | T035 |
| SC-005 | Python analysis at least 9 results (a floor), and no open `(rule, path)` disappears | T008 (prerequisite), T037 |
| SC-006 | Exactly the four required contexts from F8, unchanged in name and count | T038 |
| SC-007 | Leg within 8 minutes AND total within 2 minutes of pre-change; total bound governs | T027 |
| SC-008 | Undispositioned count at window close, BEFORE the FR-016b default, recorded as a number | T042 |
| SC-009 | Every retained rule traceable to an arm line or to the transcribed Q4 extraction evidence | T012, T017 |
| SC-010 | Probe record reproducible by a second person from the sources it names | T012 |
| SC-011 | Enforcement recommendation committed in this directory with all five named elements | T041 |
| SC-012 | The warning comment exists; no other matrix-context job lacks one | T020, T038 |
| SC-013 | Close-out outcome recorded as COMPLETE or FAILED CLOSE-OUT | T044 |

### Tasks with no requirement behind them

Five, all infrastructure, each justified:

| Task | Why it has no FR or SC | Justification |
|---|---|---|
| T001 | Environment pinning | Required by the campaign rule against `create-new-feature.sh`; not a feature behaviour |
| T002 | Remote ref existence | Not in any artifact. Added because a missing ref and an absent dispatch permission fail identically, and FR-009c would record the wrong one |
| T003, T004 | Artifact corrections | AR#2 findings 12, 13, 14, 17, 18, 19, 21, recorded as "fix before implementation" but never given a step |
| T004a | Runbook correction | Cross-Artifact section E recorded eleven mechanical defects in `quickstart.md` and closed with a sentence saying it "should be updated", which is not a step. It is the only artifact whose commands get pasted into a shell verbatim |
| T005 | Substituted pre-push gate | `make validate` cannot pass on this tree; without this the `plan.md` §8 row is false |
| T006 | Evidence log creation | Every record-writing FR presupposes the file exists; no requirement says who creates it |

---

## Cross-Artifact Analysis

Scope: `spec.md`, `plan.md`, `quickstart.md`, `checklists/requirements.md`, and this `tasks.md`.
Method: forward coverage (every FR and SC to a task), reverse coverage (every task to a requirement),
step-by-step comparison of `quickstart.md`'s Phases A-F against this file's phases, and re-execution
of every empirical claim that could be checked read-only from the working tree.

### A. Requirement coverage gaps

**None.** 33 of 33 functional requirements and 13 of 13 success criteria map to at least one task, per
the two tables above. Verified by extracting the requirement identifiers from `spec.md` and diffing
against the coverage table.

Two coverage observations that are not gaps but are worth stating:

- **A1 (LOW)**: FR-004's second clause ("if the first run contradicts F9, the prerequisite MUST be
  stated explicitly and provisioned") has no positive trigger. It fires only if the leg fails for a
  build reason, which T022's pass condition deliberately does not treat as a stop. This is correct:
  a failing leg is a result, and T022 records it. But no task tells the operator what "provisioned"
  would mean, because nothing in the artifacts does either. Accepted as an untriggered branch.
- **A2 (LOW)**: FR-009a's positive control is now folded into the OPTIONAL B2 arm (T015, T016). Its
  original mandatory-first-arm semantics survive only in the sense that a zero result declares
  INCONCLUSIVE. That is a faithful reading of FR-009b's amendment, but FR-009a's own text still says
  "MUST establish a POSITIVE CONTROL before any comparison is treated as meaningful" without the
  word OPTIONAL anywhere in it. FR-009b amends it in effect; FR-009a does not say so on its face.

### B. Tasks with no requirement behind them

Five, enumerated and justified in the table above. None is scope creep: T001, T005 and T006 are
prerequisites that the artifacts assume without assigning, T002 closes a misdiagnosis path this
analysis found, and T003/T004 execute corrections AR#2 explicitly deferred to implementation time.

### C. Ordering hazards

- **C1 (HIGH, found here, not in any artifact)**: `quickstart.md` Phase A1 runs
  `gh workflow run "$WF" --ref "$BR"` as the FIRST command in the runbook. Verified on this working
  tree: `git branch -a` shows a local `001-codeql-coverage` and NO `remotes/origin/001-codeql-coverage`.
  `gh workflow run --ref` resolves the ref server-side, so this dispatch fails with a ref error, not a
  permission error. `plan.md` A1's "If no" branch and FR-009c would then record `DISPATCH AVAILABLE:
  no` and downgrade the whole feature to post-merge evidence on the strength of a misdiagnosis.
  **Resolved** by T002, which gates T007 on `git ls-remote --exit-code --heads origin "$BR"`, and by
  T007's explicit instruction to re-check T002 before recording a negative.
- **C2 (MEDIUM)**: `quickstart.md` A1's dispatch is presented in a runbook whose header says
  "Commands are read-only unless marked MUTATES". A1 is unmarked, but it starts a real CI run. Harmless
  in effect (the matrix is still Python-only and the config is unmutated at that point) but it is a
  state change, and the run it produces sits in the same `refs/heads/001-codeql-coverage` analyses
  list that T016 and T023 later filter. T007 records its run id so the later filters can distinguish it.
- **C3 (MEDIUM)**: FR-021 requires the close-out date at CAPTURE time, and Deferral 2 must therefore
  be answered before capture. `quickstart.md` states this correctly in prose ("Ask the owner BEFORE
  Phase E") but its Phase A code block contains no step that actually asks, and neither does
  `plan.md` A3. A prose instruction with no step is how a deadline gets missed. **Resolved** by T009,
  which is a task with an owner, a trigger, a two-valued pass condition, and a named fallback.
- **C4 (MEDIUM)**: `plan.md`'s Phase D says D2's registry entries are "owed at merge, not at
  close-out", but `quickstart.md`'s Phase D section sits AFTER the merge instruction with no ordering
  statement, and the identifier-reading command it gives (`grep ... | tail -1`) is a point-in-time
  read whose answer is stale the moment another feature merges. **Resolved** by T032's explicit
  "read the highest value at the moment you write, not at the moment you read this file", and by
  T044 repeating the read for the conditional third entry.
- **C5 (LOW)**: T037 clause 2 consumes `/tmp/a2-prechange.json` written at T008, which may be several
  days earlier and in a different shell. `/tmp` survives that on most systems but not all. Mitigated
  by T008's instruction to paste the list into the evidence log, which is the durable copy; the
  temporary file is a convenience.

### D. Unfalsifiable or weak pass conditions

Swept for the campaign's known class: a check whose PASS value is ZERO or EMPTY is not a check unless
the read is proven to have succeeded.

- **D1 (HIGH, present in `quickstart.md`, fixed here)**: `quickstart.md` has FOUR checks whose pass
  value is zero or empty, and all four guards are ADVISORY only. B1's guard is
  `[ "$rc" -eq 0 ] && [ -s /tmp/py-main.log ] || { echo "... STOP."; }` and the Phase C guard has the
  same shape. The word STOP appears in the message; nothing stops. Execution continues into the
  zero-valued checks and every one of them renders as a pass. A2's guard ends in a bare `false`, which
  sets an exit status nobody reads. **Fixed** in T011, T024, T008, T016, T033 and T034, all of which
  use `|| { echo ...; exit 1; }`.
- **D2 (HIGH, found here)**: `quickstart.md` A2 and E2 both use `gh api --paginate --jq '[...]'` with
  an AGGREGATING filter. `gh` applies `--jq` per page and concatenates, so a multi-page result emits
  one array (A2) or one object (E2) PER PAGE rather than one for the whole set. Downstream `jq` then
  reads only the first, or errors. This bites precisely when the baseline is large, which is the
  outcome this feature explicitly EXPECTS. **Fixed** in T008, T033 and T034 by
  `--paginate --slurp > file` followed by a separate `jq '[.[][] | ...]'`. `--slurp` is available
  (verified: `gh version 2.89.0`).
- **D3 (HIGH, found here)**: `quickstart.md` E2's partition is `js/` plus `py/` and is NOT exhaustive.
  The Python leg's own coverage summary reads "152 out of 154 Python files **and 5 out of 5 GitHub
  Actions files**", so `actions/`-prefixed alerts are reachable and would fall into neither bucket,
  silently dropping out of both the baseline and the SC-004 delta. **Fixed** in T034 by adding an
  `other` bucket and a `partition_check` assertion that the three buckets sum to `total_open`.
- **D4 (MEDIUM)**: `quickstart.md` C phase tier 1 prints two counts without their `PIPESTATUS[0]`,
  unlike B1 which does print it. A zero count from `grep -c '/frontend/'` after a first grep that
  matched nothing is indistinguishable from a real zero. **Fixed** in T025 by printing
  `first-grep rc` for both tier-1 counts.
- **D5 (MEDIUM)**: SC-012's second clause ("the workflow contains no OTHER job whose status context
  is generated per matrix value without one") has no command anywhere in `quickstart.md`. A "none
  found" with no enumeration is unfalsifiable. **Fixed** in T020 and T038, which require the `matrix:`
  enumeration to be recorded.
- **D6 (MEDIUM)**: SC-005's second clause is stated in every artifact but no artifact gives the diff
  command. `quickstart.md` E3 checks only the results_count floor. **Fixed** in T037 clause 2.
- **D7 (LOW)**: `quickstart.md` E3's SC-006 check reads `.contexts`, which GitHub deprecated in favour
  of `.checks`. It is still populated today, so the check works, but it will silently return null if
  the API drops it, and null is not four contexts. **Fixed** in T038 by printing both shapes.
- **D8 (LOW)**: T025 tier 2's pass condition remains partly judgemental ("both directories being under
  the scan root and matching no exclusion establishes scope"). It cannot be made fully mechanical
  because the JavaScript extractor's default per-file logging behaviour is genuinely unknown in
  advance, which Q3 states honestly. The anti-false-negative rule is what keeps the residual
  judgement safe: the only two recordable values are PROVEN and UNPROVEN, and UNPROVEN does not fail
  the merge gate.

#### D9. Pagination truncation, swept as a class (coordinator note, mid-flight)

The class: **a `gh api` collection read without `--paginate` truncates at the default page size, and
truncation renders as CLEAN.** Measured campaign-wide on this repository: the all-states code-scanning
corpus is 137 items, the open alerts sit at numbers 144 to 150, past the end of page one, and an
unpaginated `state=open` query returns ZERO. This is the same failure DIRECTION as the empty-log class
in D1, arriving through a different door, so it was swept as a class rather than grepped as a symptom.

Every `gh` call that reads a collection in this feature directory, with its verdict:

| Where | Call | Collection? | Verdict |
|---|---|---|---|
| tasks T008 | `alerts?state=open` | yes | CLEAN as authored: `--paginate --slurp`, `exit 1` guard, `jq length` floor |
| tasks T016 | `analyses?ref=$BR` | yes | **HIT, fixed**: was `per_page=10`, no `--paginate`, no guard |
| tasks T023 | `analyses?ref=$BR` (SC-002) | yes | **HIT, fixed**: was `per_page=10`, no `--paginate`. Worst of the three, because an absent JavaScript/TypeScript entry is SC-002's stated failure value, so truncation would have failed a leg that ran |
| tasks T027 | `run view --json jobs` | yes (jobs) | **HIT, fixed**: no guard; a missing leg would have read as a fast leg |
| tasks T030 | `alerts?state=open` | yes | **HIT, fixed. This was the exact `CLAUDE.md:622` shape, copied in from the Pre-Push Checklist**, which has been certifying a clean repository over five open alerts |
| tasks T032, T044 | `issue list` | yes | **HIT, fixed**: `--limit 10` and bare `--limit`, both under the 30 default |
| tasks T033, T034 | `analyses` / `alerts` on `main` | yes | CLEAN as authored: `--paginate --slurp` plus guards |
| tasks T007, T022 | `run list --limit 3` / `--limit 1` | yes | CLEAN: the pass value is a non-empty match, so truncation is a false NEGATIVE, and T022 carries a `[ -n "$RUN" ]` floor |
| tasks T011, T024 | `run view --log` | no (blob) | CLEAN: rc plus `-s` plus a line-count floor |
| tasks T016 | `analyses/{id}` SARIF | no (object) | CLEAN: rc plus `-s` |
| tasks T038 | `required_status_checks` | no (object) | **HIT, fixed**: single object so pagination does not apply, but the null floor was missing and a dropped field would have satisfied "no unexpected context" vacuously |
| quickstart A2, E2 | `alerts` | yes | `--paginate` present. This is what the sibling audit praised, and the praise is correct for the ALERTS queries |
| quickstart B2, C, E1, E3 | four `analyses` queries | yes | **NOT CLEAN. The praise did not extend this far.** All four are unpaginated `per_page=10` or `per_page=30` |

**The one that matters most is `quickstart.md` E1**, which is unpaginated `per_page=30` followed by
`sort_by(.created_at) | .[0]`. The API returns newest first, so that expression yields the oldest of
the 30 NEWEST analyses, not the oldest overall. Once more than 30 analyses accumulate on
`refs/heads/main` after merge, E1 selects the wrong JavaScript/TypeScript analysis, and that
identifier is what **starts the A1 triage clock and is written into the baseline record under
FR-021**. A clock started from the wrong analysis is a wrong close-out date in a record whose whole
purpose is to make the deadline checkable. Fixed at T033 by `--paginate --slurp` before the sort.

**Interaction with this feature's own premise, flagged per the coordinator.** Every count-based
statement in this feature now has TWO independent ways to be wrong, and neither may render as
success: a truncated read makes a count too LOW, and this feature's own leg makes it legitimately
HIGHER. The two are indistinguishable from the number alone. Three places carry count-based
reasoning and each now records the read's completeness beside the number: T030 pass condition 4
(pre-push open count), T035 (the SC-004 before/after delta), and T042 (the SC-008 undispositioned
count, which is derived from T034's guarded read rather than from a fresh query). A low count is
never recorded as good news anywhere in this file.

### E. Quickstart versus tasks disagreements

Recorded as findings, not smoothed over. In each case this file departs deliberately and says why.

| # | `quickstart.md` says | This file says | Why |
|---|---|---|---|
| E1 | A1 dispatches first, no ref check | T002 checks `git ls-remote` first | C1: the branch is not on origin, so A1 fails for the wrong reason |
| E2 | Guards echo "STOP" and continue | T011/T024/T008/T016/T033/T034 `exit 1` | D1: the campaign's zero-is-pass rule |
| E3 | `--paginate --jq '[...]'` | `--paginate --slurp` then a separate `jq` | D2: per-page filter application breaks on the expected large baseline |
| E4 | E2 partitions `js/` and `py/` | T034 adds `other` and a `partition_check` | D3: GitHub Actions rules fall through both buckets |
| E5 | Tier 1 counts without `PIPESTATUS[0]` | T025 prints it for both | D4: a first-grep miss reads as a real zero |
| E6 | SC-006 reads `.contexts` only | T038 reads `.contexts` and `.checks` | D7: deprecated field |
| E7 | "Ask the owner BEFORE Phase E" as prose | T009 is a task with an owner and a two-valued pass condition | C3: prose is not a step |
| E8 | Phase D registry read is a single `grep ... tail -1` | T032 and T044 both re-read at write time | C4: the value is stale on any concurrent merge |
| E9 | Skeleton says "FR-007 / FR-007a: ... argued or carded" as open work | T014 TRANSCRIBES Q4's argument | AR#2 finding 14, only partly fixed in `plan.md` |
| E10 | Four `analyses` queries unpaginated (`per_page=10` or `30`) | T016, T023, T033 use `--paginate --slurp` | D9: truncation renders as clean; E1's `sort_by \| .[0]` picks the WRONG analysis and starts the A1 clock late |
| E11 | No guard on `run view --json jobs` (SC-007) | T027 guards and asserts the leg is present | D9: a missing leg reads as a fast leg |

None of these is a contradiction in intent. Every one is a mechanical defect in a command or a
missing step, and `quickstart.md` should be updated to match this file before execution.

### F. Contradictions across artifacts

- **F1 (MEDIUM, unfixed in `plan.md`, routed to T004)**: `plan.md`'s Constitution Check §8 row asserts
  "`make validate` before push. **PASS**". `make validate` cannot pass on this tree:
  `scripts/check-banned-terms.sh` exits 1 on pre-existing matches from other features' directories.
  The row is aspirational, and a task that depended on it would block forever. T005 defines the
  substituted gate; T004 item 5 corrects the row.
- **F2 (MEDIUM, unfixed in `spec.md`, routed to T003)**: AR#2 finding 12 stands. Three passages in
  User Story 2 still assert the contradiction is unproven, which is what F3 said BEFORE Q4 replaced
  it. A reader reaching User Story 2 before the Clarifications appendix gets the pre-Q4 story from the
  same file that carries the post-Q4 fact.
- **F3 (LOW, unfixed in `spec.md`, routed to T003)**: User Story 2's Independent Test cites "FR-007
  through FR-009" for the probe. FR-007 and FR-007a are the `frontend/tests` scope decision. The probe
  is FR-008 through FR-010a.
- **F4 (LOW, unfixed, routed to T003)**: F3 cites `codeql-config.yml` "lines 19 to 30"; the file is 29
  lines. Q4 cites 23 to 29 correctly, so the spec carries the wrong and the right citation for the
  same block.
- **F5 (LOW, unfixed, routed to T003/T004)**: three renderings of one measured number. `plan.md`
  Scale/Scope and F10 say about 47,300; `plan.md`'s §3 Constitution row says "about 0 to about
  48,000"; two `spec.md` review passages say "about 48,000". Measured is 47,298.
- **F6 (MEDIUM, AR#2 is itself WRONG)**: AR#2 finding 18 claims the Playwright rename warning is at
  `pr-checks.yml:389-393` and that `plan.md` D-7's citation of 390-394 is "off by one at both ends".
  Re-measured on the working tree: line 389 is a bare `#`, the warning paragraph is exactly 390 to
  394, line 395 is the `# ====` rule, line 396 opens `playwright-e2e:`. **D-7's citation is correct as
  authored and must not be "corrected".** T004 item 4 records the refutation next to D-7 so the next
  reader does not apply a wrong fix.
- **F7 (LOW)**: `plan.md`'s documentation tree calls `spec.md` "897 lines". Measured now: 898. AR#2
  finding 11 already moved this number once (from 613 to 860) and it has drifted again. The fix is to
  stop citing a count that changes on every edit, which T004 item 1 does.
- **F8 (MEDIUM)**: `checklists/requirements.md` is unchanged since authoring and is the only artifact
  with zero traceability to the other four. It certifies "Requirements are testable and unambiguous"
  over a spec in which AR#2 finding 2 found two MERGE-gate criteria unsatisfiable, and its closing
  line still reads "Items marked incomplete require spec updates before `/speckit.clarify` or
  `/speckit.plan`" when both have already run and a second adversarial review has landed since. AR#1
  finding 19 and AR#2 finding 16 both recorded this and both deliberately declined to fix it. **This
  analysis does not overturn that decision either, but notes the certification has now survived two
  adversarial reviews, one clarification session, and a task breakdown without being re-examined.**
  It is the weakest artifact in the feature.

### G. Verified clean

Recorded because a reviewer reporting only hits is not distinguishable from one who did not look.

- **No task runs FR-009b arm 1 or arm 2.** Swept every task, every embedded command, and every
  conditional branch. The only configuration mutation before Phase C is T016, which is explicitly
  the single OPTIONAL control arm removing BOTH rules, gated behind T015's recorded decision, and
  T015 carries the prohibition verbatim. T017 reverts it. No `probe(001): codeql config arm N` loop
  exists anywhere in this file.
- **No task treats a rising alert count as failure, and no task sets a ceiling.** Swept every pass
  condition, every checkpoint, and every dependency note, not just the SC block. T035's pass condition
  states explicitly that an increase satisfies SC-004. T037 clause 2 checks only for DISAPPEARANCE and
  states that `appeared` being non-empty is the point of the feature. T030's pass condition 4 records
  the pre-existing alert listing and says in the same sentence that it is not a gate. The only numeric
  floor in the file, T037's "at least 9", is a per-analysis results count on the Python leg, not a
  repo-wide alert count, and is a floor rather than an equality for the reason AR#1 finding 6 recorded.
- **No check keys on a CodeQL alert NUMBER changing state.** Swept beyond the SC block into the
  acceptance-scenario-derived tasks and the dependency notes. T008, T034, T037 and T039 all key on
  `rule@path`. Numbers appear in exactly one role, as a lookup convenience, and T008 and T034 both say
  so inline. The alerts API exposes nothing finer than `path` plus line and column offsets under
  `most_recent_instance.location`, so no task demands more than is mechanically available.
- **The two-moment capture is preserved, and the same-ref caveat is applied only where it belongs.**
  T016 reads per-analysis SARIF via `analyses/{id}` with `Accept: application/sarif+json`, because it
  compares two analyses of ONE reference and `most_recent_instance` is overwritten by the later run.
  T008 and T034 are two captures at two different MOMENTS and correctly use the alerts endpoint; T016
  states the distinction inline so a later reader does not "fix" a valid capture.
- **Every collection read is paginated and floored.** Swept as a class per D9, not grepped as a
  symptom: 13 call sites across `tasks.md` and `quickstart.md`, each classified as collection or
  single object, each checked for `--paginate`, an explicit exit-code check, and a non-empty or
  non-null floor wherever emptiness is the pass value. Six hits in `tasks.md`, all fixed in place.
  Four unpaginated `analyses` queries remain in `quickstart.md` and are recorded at E10 for the
  runbook update.
- **No task requires `make validate` to exit 0.** T005 substitutes a scoped banned-terms check on this
  feature's own directory, and T030 uses that substitution rather than the full target.
- **No `npm install` anywhere.** T021's pass condition greps for it and requires zero hits inside the
  `codeql` job block. No task proposes one, and FR-004b's constraint is carried into T041.
- **No banned term and no em-dash** in this file. The seven banned terms
  (`scripts/check-banned-terms.sh`) do not appear.
- **The established facts hold.** Re-measured read-only: the matrix `language: ['python']` is at
  `.github/workflows/pr-checks.yml:294`, the `codeql:` job block opens at 282, `fail-fast: false` is
  already present at 292; `git ls-files` returns 291 tracked JavaScript and TypeScript files, 290 in
  scope after the root-anchored exclusion, and 393 Python files under `tests/`;
  `docs/reference/TECH_DEBT_REGISTRY.md` exists with `TD-023` as its highest identifier;
  `.github/codeql/codeql-config.yml` is 29 lines with the false comment at line 13, `paths-ignore` at
  19 to 20 and `query-filters` at 23 to 29; the workflow declares `workflow_dispatch`, `push` on
  `main` and `dependabot/**`, `pull_request` on `main`, and a Monday 09:00 UTC schedule.

### Verdict

**READY WITH PREREQUISITES.** Requirement coverage is complete: 33 of 33 functional requirements and
13 of 13 success criteria, with no gaps and five justified infrastructure tasks. Zero CRITICAL. Five
HIGH, all of them defects in commands rather than in the design, and all five are fixed inside this
file (C1 by T002, D1 by the exit-1 guards, D2 by `--slurp`, D3 by the exhaustive partition, D9 by the
pagination sweep). Eight MEDIUM and eight LOW, of which six are routed to T003 and T004 as
pre-implementation artifact corrections and one, F6, is a refutation of an AR#2 finding that must NOT
be applied.

The prerequisites are Phase 0. Do not begin Phase A until T002 has confirmed the remote ref, T003 and
T004 have landed the artifact corrections, and T005 has replaced the unreachable `make validate` gate.
`quickstart.md` should be updated to match section E before anyone executes from it, because the
disagreements there are mechanical defects in commands an operator would run verbatim.

---

## Adversarial Review #3

Final gate before implementation. Reviewer authored none of these artifacts. Method: **execute, do
not read.** Every read-only command `tasks.md` prescribes was run against the live repository and the
live GitHub API on 2026-07-30. Findings below distinguish RAN from READ throughout. Prior review
appendices are append-only history and are not rewritten here.

### Verdict

**READY FOR IMPLEMENTATION**, after the fixes recorded below, which are applied in this file.

The previous stage's **READY WITH PREREQUISITES** was correct in spirit and incomplete in fact. Two
of its five stated prerequisites were not discharged by any task, and three prerequisites it did not
name at all were discovered by execution. All five HIGH findings below are fixed in place; the
feature is executable start to finish once Phase 0 runs.

### Findings

#### HIGH

- **AR3-1. T033's SC-001 pass condition was vacuously satisfiable, and T033 is where the triage
  clock starts.** RAN, against the live corpus. `refs/heads/main` carries **948** code-scanning
  analyses, every one of them `/language:python`. T033's filter,
  `[... select(.category | test("javascript"))] | sort_by(.created_at) | .[0] | {id, category, ...}`,
  over that empty selection prints `{"id":null,"category":null,"created_at":null,...}`. Its `type` is
  `"object"`; `. == null` is `false`. The pass condition read "a non-null object is printed", so an
  operator following it verbatim records SC-001 as SATISFIED with zero JavaScript/TypeScript analyses
  in existence, and then T036 writes `null` into the FR-021 baseline record as the identifier that
  starts the 10-working-day clock and computes the close-out date. This is the same failure DIRECTION
  as the pagination class the previous stage swept, arriving through the door it did not check:
  the read succeeded, the guard passed, the pagination was correct, and the RESULT was still empty.
  **FIXED**: an explicit `N > 0` count floor with `exit 1`, a null-guard on `.category` before
  `test()` (`null | test(...)` aborts the filter rather than skipping the row), and a pass condition
  that names the count as the check.
- **AR3-2. T037 clause 2 collapses duplicate `rule@path` keys, so a partial regression passes
  SC-005.** RAN and DEMONSTRATED on live data. `rule@path` is not unique in the current open set:
  of the five open alerts, **three share one key**,
  `py/clear-text-logging-sensitive-data@src/lambdas/ingestion/handler.py` (numbers 148, 149, 150).
  jq's array `-` removes every occurrence of each right-hand element, so a key dropping from three
  members to one subtracts away completely. Executed: deleting 149 and 150 from the pre-change
  capture and running the authored clause-2 filter emits `{"disappeared": [], "appeared": []}`. Two
  open HIGH-severity alerts vanish and a MERGE-gate criterion passes. The `(rule, path)` identity
  decision is right and is not what failed; treating a multiset as a set is. **FIXED**: clause 2 now
  tallies multiplicity and reports a `shrunk` bucket. Re-executed on three cases: unchanged emits all
  three arrays empty; partial loss emits `shrunk: [{before: 3, after: 1}]`; full loss emits both
  `shrunk` and `disappeared`.
- **AR3-3. The `tech-debt` label does not exist in this repository, and T032 is a merge-gate task
  that requires it.** RAN. `gh label list --limit 100` returns **13** labels: `bug`, `documentation`,
  `duplicate`, `enhancement`, `good first issue`, `help wanted`, `invalid`, `question`, `wontfix`,
  `dependencies`, `python`, `github-actions`, `terraform`. `tech-debt` is absent. Consequently
  `gh issue list --label tech-debt --json number,title --jq 'length'` returns `0`, which reads as a
  clean starting count and is really a missing label, and `gh issue create --label tech-debt` fails
  outright. The §9(b) half of the merge-time obligation was unexecutable as authored, and the §9
  obligation is the one the previous stage flagged as LIVE. **RESOLVED BY OWNER DIRECTIVE**: the
  label is not to be created and no issue is to be raised against it. T032 and T044 write the
  registry entries (§9(a)) and record the §9(b) half as outstanding.
- **AR3-4. Eleven recorded defects in the operator runbook, discharged by a sentence.** The
  Cross-Artifact Analysis closed section E with "`quickstart.md` should be updated to match section E
  before anyone executes from it" and gave that sentence no task. T003 corrects `spec.md`, T004
  corrects `plan.md`, and nothing corrected `quickstart.md`, the one artifact in the feature whose
  commands are pasted into a shell verbatim, and the first document an operator opens at Phase A.
  RAN, confirming every defect is live: `quickstart.md:215-216` and `:230-231` are unpaginated
  `per_page=30`, `:105-106` and `:150-151` are `per_page=10`, `:36-38` and `:222-227` use
  `--paginate` with an aggregating `--jq`, `:84` and `:162` are guards that print STOP and continue,
  `:39` ends in a bare `false`, `:226-227` is the non-exhaustive two-bucket partition.
  **FIXED**: added **T004a**, `[P]` with T003 and T004, with five mechanical pass conditions.
- **AR3-5. No task puts HEAD on the feature branch, and the artifacts are untracked, so T030 can
  never pass.** RAN, three legs, all three open. `git rev-parse --abbrev-ref HEAD` prints `main`.
  `git rev-list --count main..001-codeql-coverage` prints **`0`**. The local branch exists but is an
  exact ancestor of `main` with no unique commits. `git ls-files specs/001-codeql-coverage/` prints
  **`0`**. All five artifacts are untracked. T001's pass condition asserted HEAD was already on the
  branch and instructed the operator to "stop" otherwise, supplying no step that gets there. T002's
  remedy, `git push -u origin HEAD`, executed in the state actually measured, pushes `main` and
  creates no feature ref. And because T016 and T022 both commit with `git commit -S -am`, which
  stages modifications to TRACKED files only, the artifacts would never enter the diff, making
  T030's pass condition 2, which REQUIRES `specs/001-codeql-coverage/` in
  `git diff --stat origin/main..HEAD`, unsatisfiable after all of Phases B and C are already done.
  **FIXED**: T001 switches to the branch, T002 tracks and commits the artifacts before pushing and
  re-checks `ls-remote` after.

#### MEDIUM

- **AR3-6. T021's pass condition fails on a correct tree.** RAN:
  `grep -c 'npm install\|npm ci\|yarn install\|pnpm install' .github/workflows/pr-checks.yml` prints
  **`2`**, not `0`. Both hits are `cd frontend && npm ci` at lines 424 and 511, in the frontend-test
  and Playwright jobs. The prose scoped the check to the `codeql` job; the command scanned the whole
  file. A check that fails on a correct tree trains the operator to wave the next one through.
  **FIXED**: the grep is scoped by content-anchored job-block extraction. Re-executed: the block
  resolves to lines 282 to 317 and the scoped count prints `0`.
- **AR3-7. T013's pass condition had no target value.** RAN:
  `grep -cE '^\s*-|^[a-z-]+:' .github/codeql/codeql-config.yml` prints **`6`** (lines 15, 19, 20, 23,
  26, 29), because the pattern also catches `name:` and every list item. Six was offered as
  confirmation that the file "carries exactly the two rule blocks", with no stated expectation, so
  there was nothing to compare against and no way to fail. **FIXED**: the count now targets top-level
  rule keys only and must print exactly `2`. Re-executed: prints `2`, with three top-level keys.
- **AR3-8. T004's guard against re-applying the one finding that must NOT be applied was inert.**
  RAN: T004's pass condition greps `389-394`, a string appearing nowhere in `plan.md` before or after
  the fix. The only hits that grep produced came from its other two alternatives, at lines 59, 136,
  398 and 401. AR#2 finding 18's wrong number is `389-393`, and it legitimately sits at `plan.md:402`
  as append-only review history, so a file-wide grep for it would false-positive. As authored, an
  implementer who "corrected" D-7 to `389-393` would have passed T004. **FIXED**: the check is scoped
  to the D-7 block. Re-executed: 1 hit for `390-394`, 0 for `389-393`.
- **AR3-9. T006 instructs copying four skeletons from a section containing three.** READ and
  verified: `quickstart.md`'s "Record skeletons" holds `## Probe record`,
  `## Pre-merge verification` and `## Baseline record`; the close-out fields (SC-008 count, SC-013
  outcome, §9 entries) are folded into the baseline skeleton with no heading of their own. T006's
  pass condition demands at least four `^## ` headers, so an operator copying faithfully produces
  three and fails, with nothing left to copy. **FIXED**: T006 names the fourth header and says to
  write it by hand until T004a lands; T004a item 9 adds it to the runbook.
- **AR3-10. T029 does not distinguish `rc=2` from `rc=1`.** Its pass condition is "`rc=1` (no
  matches)". If the evidence-log path is wrong or the file unreadable, `grep` returns `2` and matches
  nothing, and the FR-018 provenance audit certifies clean on a read that did not happen. T003 and
  T026 both handle `rc=2` explicitly; the one task whose entire job is auditing evidence provenance
  does not. NOT FIXED (MEDIUM, one-line fix at implementation time: accept `rc=1` only, and treat
  `rc=2` as re-run).
- **AR3-11. T045's justification for not closing at merge is factually wrong about SC-004.** It
  states that "SC-004, SC-008, SC-011 and SC-013 cannot be satisfied until the close-out date".
  SC-004 is satisfied by **T035**, which runs in Phase E immediately after merge, months before the
  close-out date. Three of the four claims hold and the conclusion (do not close at merge) is right;
  the fourth is false and weakens a load-bearing argument. NOT FIXED (drop SC-004 from that sentence).

#### LOW

- **AR3-12. Cross-Artifact finding F7 is wrong, and this is the second such case in this feature.**
  F7 claims `spec.md` is "Measured now: 898" and that `plan.md`'s "897 lines" has "drifted again".
  RAN: `wc -l` prints **897**, `wc -c` prints 82853, the final byte is `0a`, and `grep -c ''` also
  prints **897**. `plan.md`'s citation is CORRECT and has not drifted. This is a second instance of
  a review stage asserting a discrepancy that does not reproduce (AR#2 finding 18 was the first, and
  the previous stage caught it). T004 item 1's policy of stating the appendices instead of a count is
  still worth doing; its premise that the number has drifted is not true.
- **AR3-13. T003 item 5 has no determinate target and points away from the repository's actual
  convention.** It says to set `spec.md` Status "to the repository's convention for a planned
  feature". RAN, across all specs: **191** say `Draft`, 8 `Complete`, 5 `Implementation`, 4
  `Draft (planning only ...)`, 2 `Implemented`, and one each of `Planned`, `Ready for Implementation`
  and three others. `Draft` IS the convention by an order of magnitude. T003's own pass condition
  does not check item 5 at all, so it passes either way.
- **AR3-14. `quickstart.md`'s skeleton preamble says "Both live in `evidence-log.md`"** over three
  skeletons, and omits `enforcement-recommendation.md` (T041) entirely. Folded into T004a item 9.
- **AR3-15. `ID=<analysis id for this arm, matched by commit_sha ...>` at T016 is not valid shell**
  and will error if the block is pasted whole. Same at `quickstart.md:111`. Obvious to a human, but
  the block is otherwise designed for paste-and-run.

### Prerequisites behind READY WITH PREREQUISITES, each with its discharge status

The previous stage named five. Execution found three more it did not name. All eight below.

| # | Prerequisite | Named by AR#2/CAA? | Discharged by | Status |
|---|---|---|---|---|
| P1 | Remote feature ref exists (T002) | yes | T002 | **WAS NOT DISCHARGED.** `ls-remote` rc=2 confirmed. Deeper than stated: branch has zero unique commits and the artifacts are untracked, and T002's remedy pushed `main`. **Now discharged** by the rewritten T001 + T002 (AR3-5) |
| P2 | `spec.md` corrections | yes | T003 | Discharged by a task. Item 5 indeterminate and unchecked (AR3-13), which is cosmetic |
| P3 | `plan.md` corrections | yes | T004 | Discharged by a task. Its anti-regression guard was inert (AR3-8); **now fixed** |
| P4 | Substituted pre-push gate | yes | T005 | **GENUINELY DISCHARGED.** RAN verbatim: script rc=1 whole-tree as predicted, `grep -c 'specs/001-codeql-coverage'` prints `0` with `grep` rc=1, `/tmp/banned-before.txt` non-empty at 25 lines. Works exactly as written |
| P5 | `quickstart.md` updated to match section E | yes, **as a sentence only** | nothing | **WAS NOT DISCHARGED. This is the prerequisite that leaked hardest**: eleven live defects in the runbook, no task. **Now discharged** by T004a (AR3-4) |
| P6 | `tech-debt` label exists | no | nothing | **NOT NAMED, NOT DISCHARGED.** **Withdrawn as a prerequisite** by owner directive: the label is not to be created, so no task depends on it (AR3-3) |
| P7 | A fourth record skeleton exists to copy | no | nothing | **NOT NAMED, NOT DISCHARGED.** **Now discharged** by T006 + T004a item 9 (AR3-9) |
| P8 | Deferral 2: owner confirms the 10-working-day window | yes | T009 | **CANNOT be discharged before implementation, and is handled honestly.** It has a named owner, a raise point, a hard deadline at T036, a two-valued pass condition and a stated fallback that names its own cost. This one leaks by design |

**Answer to the question the mandate asks**: seven of the eight are satisfiable before implementation
starts and are now discharged by tasks rather than by sentences. The eighth, P8, genuinely cannot be
and is the only prerequisite that legitimately leaks into implementation.

### The `analyses` endpoint queries (E1 and its siblings)

RAN, at real scale. `refs/heads/main` carries **948** analyses.

- The E1 defect reproduces exactly as the previous stage described. Unpaginated `per_page=30` then
  `sort_by(.created_at) | .[0]` yields `2026-07-25T21:47:22Z` (id 1527408350). The true oldest across
  all 948 is `2025-11-20T00:27:17Z` (id 799932039). An **eight-month** error in the value that
  becomes the FR-021 deadline.
- **T033 closes the pagination half and did NOT close the emptiness half.** `--paginate --slurp` is
  present and correct; the pass condition was vacuous (AR3-1). Now closed.
- **No sibling repeats the pagination bug.** Swept every `analyses` read in `tasks.md`: T016 sorts
  but extracts no `.[0]` and is paginated; T023 filters without sorting and is paginated, and its
  `total > 0` floor independently catches the empty case (RAN against the non-existent branch ref:
  `gh` exits **0** and writes a 4-byte `[[]]`, so the `-s` guard passes and only the `total` floor
  stops it); T037 clause 1 reads T033's already-paginated file. Four unpaginated `analyses` reads
  remain in `quickstart.md` and are now T004a's item 1.
- **T037 clause 1 shares AR3-1's shape** (`sort_by | reverse | .[0] | {…}` renders an all-null object
  on an empty array) but is low risk because the Python selection is never empty. RAN: it returns
  `{"id":1551613089,"created_at":"2026-07-30T21:06:04Z","results_count":9}`. The `at least 9` floor
  is met exactly today, so any Python coverage loss shows immediately.

### Campaign facts, re-executed rather than assumed

| Fact | Result |
|---|---|
| Canonical alerts query | `gh_exit=0`, `jq 'add \| length'` = **5**, corpus 137 (117 fixed, 15 dismissed, 5 open) |
| `--slurp` rejected with `--jq` on gh 2.89 | CONFIRMED: `the --slurp option is not supported with --jq or --template`, exit 1. `gh version 2.89.0` |
| `--paginate` without `--slurp` applies `--jq` PER PAGE | CONFIRMED: `per_page=50` over 137 items emits **`50`, `50`, `37`** as three separate results |
| Matrix at `pr-checks.yml:294` | CONFIRMED. `codeql:` at 282, `fail-fast: false` at 292, `queries: security-extended` at 304, `category:` at 313 |
| Playwright warning block is 390-394, D-7 is right, AR#2 finding 18 is wrong | CONFIRMED by execution. 389 is a bare `#`, 390-394 is the paragraph, 395 is the `# ====` rule, 396 opens `playwright-e2e:` |
| Required contexts are exactly four | CONFIRMED: `.contexts` and `.checks[].context` both list `Secrets Scan`, `Lint`, `Run Tests`, `Playwright E2E Tests`; `n_contexts` = `n_checks` = 4 |
| T018 file counts | ALL FIVE CONFIRMED: 291 tracked, 290 in scope, 173 `frontend/src`, 101 `frontend/tests`, 6 `src/dashboard`, 393 `tests/*.py`, 544 `.py` total |
| T011 log fetch | CONFIRMED: rc=0, **2,125** lines, **287,655** bytes, matching AR#2's measurement exactly |
| T012, all five checks | ALL FIVE CONFIRMED: `--filter exclude:tests/**/*` at line **1480**; `Extracted file` = **152**; `/tests/` = **0** with first-grep rc=0; line **2067** reads "152 out of 154 Python files and 5 out of 5 GitHub Actions files"; 393 tracked Python test files |
| T025's anchoring claim | CONFIRMED: `^src/` on extracted-file lines matches **0**, unanchored `/src/` matches **136**. A line-anchored pattern is a guaranteed false negative, exactly as the task says |
| `.github/codeql/codeql-config.yml` shape | CONFIRMED: 29 lines, false comment at 13, `paths-ignore` 19-20, `query-filters` 23-29 |
| F18, npm absent from Dependabot | CONFIRMED: `.github/dependabot.yml` declares `pip`, `github-actions`, `terraform` only. Open Dependabot alerts: **99 total, 82 npm, 17 pip** |
| §10 local-SAST gap | CONFIRMED: `make sast` runs `bandit -r src/` and `semgrep ... src/` only |
| Registry state | CONFIRMED: `docs/reference/TECH_DEBT_REGISTRY.md` exists, highest identifier `TD-023`, 42 `TD-` occurrences. `docs/TECH_DEBT_REGISTRY.md` does not exist; constitution §9 cites it at lines 527, 569, 584 (Deferral 1 stands) |
| `CONTRIBUTING.md` citations | CONFIRMED: line 64 is `#### Admin Role (Project Owner: @traylorre)`, line 74 is `Respond to security incidents` |
| Workflow triggers | CONFIRMED: `workflow_dispatch`, `push` on `[main, dependabot/**]`, `pull_request` on `[main]`, cron `0 9 * * 1` |
| Only one `matrix:` in the workflow | CONFIRMED: exactly 1 occurrence, so SC-012's second clause is satisfiable and its enumeration is short |
| T034, T037, T039, T042 jq mechanics | RAN against live data: `partition_check: true`, `total_open: 5`, `jsts: 0`, `python: 5`, `other: 0`; all filters exit 0 |

**A rising alert count is success**, re-swept independently of the previous stage's sweep. No task in
this file sets a ceiling, and no pass condition treats a rise as failure. The only numeric floors are
T037 clause 1's per-analysis Python `results_count` (`at least 9`, measured at exactly 9 today) and
the read-completeness floors added for the truncation class. **FR-009b arms 1 and 2**, re-swept
across every task, every embedded command and every conditional branch, including the tasks and
commands added by this review: still not dispatched anywhere. T016 remains the single OPTIONAL
control arm behind T015's recorded gate.

### Highest-risk task

**T033.** It is the only point where SC-001, FR-019 and FR-021 converge; its output is not just a
check result but a VALUE that becomes a deadline in a committed record; it was vacuously passable
(AR3-1); it runs post-merge when the pull request is closed and attention has moved on; and nothing
downstream re-derives its identifier, so a wrong or null value there propagates into T034, T036, T039
and T042 unchallenged. Second: **T032**, which was outright unexecutable (AR3-3) and sits on the
merge gate.

### Most likely source of rework

**`quickstart.md`.** Eleven recorded mechanical defects, no repairing task until this review added
one, and it is the document an operator actually drives Phase A from. The tasks file corrected these
defects only in its own copies, which protects a reader of `tasks.md` and not an operator of the
runbook. Second: the branch and commit setup (AR3-5), whose failure surfaces at **T030**, after all
of Phases B and C are already spent.

### Adjacent defects OUTSIDE this feature's scope. CARDED, NOT FIXED.

- **`CLAUDE.md:622` Pre-Push Checklist ships the truncating alerts query.** Its
  `gh api repos/{owner}/{repo}/code-scanning/alerts --jq '.[] | select(.state == "open")'` has no
  `--paginate`. RAN: the repository's all-states corpus is 137 and the open alerts sit at numbers 144
  to 150, past page one, so the documented checklist reports a clean repository over five open HIGH
  alerts. The previous stage noted this; it belongs to the repository, not to this feature.
- **The `tech-debt` label is missing repository-wide**, and constitution §9(b) requires it of every
  feature. The owner has directed that it not be created and that the question be audited once at
  the end of the campaign, so §9(b) goes undischarged here. Any sibling that assumed the label
  existed has the same latent break. Worth a campaign-level card.
- **Constitution §9 cites `docs/TECH_DEBT_REGISTRY.md` at lines 527, 569 and 584**; the file has lived
  at `docs/reference/TECH_DEBT_REGISTRY.md` since `f8db8d2`. Already carried as Deferral 1 into T043.
- **`checklists/requirements.md` remains the weakest artifact**, certifying "Requirements are testable
  and unambiguous" and closing with "Items marked incomplete require spec updates before
  `/speckit.clarify` or `/speckit.plan`" after both have run and three adversarial reviews have
  landed. AR#1, AR#2 and the Cross-Artifact Analysis all declined to fix it. This review declines too,
  and notes it has now survived a fourth pass.

### Merge-ordering note for the sibling feature

Nothing added by this review makes `001-bad-tag-filter-dead-suppression`'s SC-002 confound harder to
manage, and one thing makes it easier: T037 clause 2 now reports per-key MULTIPLICITY. That sibling's
target, `py/bad-tag-filter@scripts/regenerate-mermaid-url.py`, is a **multiplicity-1** key in the
current open set (measured), so its disappearance is visible in both the `disappeared` and `shrunk`
buckets regardless of merge order. The confound remains a count-level question for the owner, not a
detection-level one.
