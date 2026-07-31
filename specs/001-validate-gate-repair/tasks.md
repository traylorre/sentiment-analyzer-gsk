# Tasks: Validation Gate Repair

**Branch**: `001-validate-gate-repair` | **Date**: 2026-07-30
**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/checker-cli.md](./contracts/checker-cli.md),
[quickstart.md](./quickstart.md)

## Terminology Note *(inherited, mandatory)*

This file never writes the retired framework names in full. They are called **legacy terms**. The
checker scans `specs/`, so naming them here would enlarge the corpus this feature exists to clear.
The authoritative list lives only in the checker's term array.

**Before committing any artifact produced by these tasks**, run
`bash scripts/check-banned-terms.sh 2>&1 | grep -E "^FAIL: [0-9]"` and confirm the count has not
grown. Baseline at task-generation time: 17 term-hits across 7 files.

## Counting convention *(read before any verification task)*

"17" is what the current Bash checker reports. The same corpus is 15 distinct lines and 19 raw
occurrences. **All equivalence checks in these tasks compare the set of (file, line) pairs**, never a
scalar, because a faithful rewrite reporting on a different basis would look like a regression while
a rewrite reproducing 17 exactly would have copied a quirk. See plan.md, "Counting note".

## Tests

Tests are REQUIRED, not optional. The constitution's Implementation Accompaniment Rule
(`.specify/memory/constitution.md:232-238`) requires all implementation code to carry unit tests
covering a happy path and at least one error path at 80% coverage. Three success criteria (SC-004,
SC-005, SC-006) plus SC-013 are only expressible as tests, because they require constructing
filesystem states that must not be left behind.

---

## Phase 1: Setup & Baseline

**Purpose**: Freeze the current state so every later change is measured against evidence rather than
memory. Nothing here modifies behaviour.

- [ ] T001 Capture the authoritative corpus baseline as a set of (file, line) pairs, not a count, by running `bash scripts/check-banned-terms.sh` and extracting path and line number from each reported match. Write the sorted set to `specs/001-validate-gate-repair/baseline-corpus.txt`. Do NOT include the matched line content in that file, or the baseline becomes part of the corpus.
- [ ] T002 [P] Record the per-stage exit codes of the current gate by running each prerequisite of `validate` individually (`fmt-check`, `lint`, `security`, `sast`, `check-banned-terms`, `check-test-target-headers`, `check-waitforresponse-race`) and appending the results to `specs/001-validate-gate-repair/baseline-corpus.txt` under a second heading. Expected at time of writing: two stages exit 2, the rest exit 0.
- [ ] T003 [P] Record the exemption baseline count required by SC-012. It is currently 0, since no exemption mechanism exists yet. Note it in `specs/001-validate-gate-repair/baseline-corpus.txt`.
- [ ] T004 [P] Enumerate the six paths whose names contain a legacy term, using `find` against the term list, and record them in `specs/001-validate-gate-repair/baseline-corpus.txt` with their current spelling redacted the same way this file redacts terms. Four are directories and two are files inside one of those directories.

**Checkpoint**: Baseline recorded. No repository behaviour changed.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: Build the checker and its test harness. Every user story below depends on this phase.
**No user story can start until this phase is complete.**

- [X] T005 Create `scripts/check_banned_terms.py` with the module docstring, the authoritative term array copied verbatim from `scripts/check-banned-terms.sh:10-18`, and a comment at the array recording that terms are matched case-insensitively as patterns rather than literals, that one entry contains characters behaving as wildcards, and that this behaviour is preserved deliberately because changing the term list is out of scope.
- [X] T006 Implement path canonicalisation in `scripts/check_banned_terms.py`: every discovered path resolves to a repository-relative, forward-slash form with no leading prefix, derived from the script's own location rather than the caller's working directory. This single function satisfies FR-008 and FR-027 and must be the only notion of a path in the module.
- [X] T007 Implement the file walk and Match construction in `scripts/check_banned_terms.py`, keeping `path` and `line_text` as separate values on the Match record per data-model.md. Path and content must never share a representation, which is the structural fix for FR-007. **Read bytes and skip undecodable files**, replacing the shell version's binary-file flag. The live tree contains a SQLite coverage database, editor swap files and cache directories; an unguarded text read raises on the first one, and because the checker fails closed inside a required job, a crash is a repository-wide merge outage. Add `.ruff_cache` to the exclusions, which the shell version omits.
- [X] T008 Implement self-exclusion in `scripts/check_banned_terms.py` by resolved canonical path, not by filename, since the module holds the authoritative term array and would otherwise report itself.
- [X] T009 Implement scan-scope exclusions in `scripts/check_banned_terms.py`, compared against canonical paths only. Carry over the directory exclusions from `scripts/check-banned-terms.sh:24-43`, expressed as canonical-path rules rather than filename globs. **Widen the carryover-file exclusion**: the shell version excludes `CONTEXT-CARRYOVER-*`, which does not match the `CONTEXT-CARRYOVER.md.loaded` file currently in the repository root. With the checker fail-closed in a required job, one such file containing a legacy term blocks every merge. Add an explicit guard that an empty or unreadable configuration produces a non-zero exit with a message naming the cause, satisfying FR-009 and FR-022b. Note in a comment that these are scan-scoping rules with no exemption semantics attached, per the plan's mechanism-collapse decision.
- [X] T010 Implement the reporting layer in `scripts/check_banned_terms.py` to the exact output contract in `contracts/checker-cli.md`: path, line number, matched term, offending line, and a remedy tailored by path class. Source paths are told to remove; documentation paths are told how to exempt. Every violation is reported in one run, satisfying FR-012.
- [X] T011 Implement the `--root` option in `scripts/check_banned_terms.py` so tests can scan a fixture directory. Exclusions must behave identically under any root; this option is how FR-027 is tested rather than asserted.
- [X] T011a Repoint the `check-banned-terms` target in `Makefile:97-98` from `@bash scripts/check-banned-terms.sh` to `@python3 scripts/check_banned_terms.py`. **Without this the feature cannot work**: T053 deletes the shell script and nothing else changes the recipe, so the gate would fail with a missing-file error and SC-001 would be unreachable. Found by adversarial review #3; the plan's Makefile edit list omitted it.
- [X] T012 Create `tests/unit/scripts/test_check_banned_terms.py` with fixture scaffolding built on `tmp_path`. **The test module MUST import the term array from the checker and MUST NOT write any legacy term as a literal**, or the checker will flag its own test file. Cover the happy path (a clean fixture tree passes) and one error path (a fixture with a violation fails).
- [X] T013 Prove equivalence as a **one-shot verification step, not a committed test**: run the new checker against the live repository and confirm it reports exactly the set of (file, line) pairs recorded in T001. Record the result in `specs/001-validate-gate-repair/baseline-corpus.txt`. **Do NOT commit this as a pytest case.** Phase 4 drives the live corpus to zero, so a committed assertion against the pre-remediation set would fail permanently and break `make test-unit` and the CI test job. It would also be non-hermetic, reading live repository state from a unit-test module. Found by adversarial review #3.

**Checkpoint**: Checker exists, is tested, and provably matches the old one on the current corpus.

---

## Phase 3: User Story 1 - A maintainer gets a truthful answer from the gate (P1)

**Goal**: Every stage runs, every stage reports, the exit code means what it says, and the gate does
not modify the tree.

**Independent test**: Run the gate. Confirm output contains an execution marker for all seven stages
including the two that previously never ran, and that a per-stage summary is printed. The exit-0 half
of this story completes after Phase 4 remediation, which is expected and noted in Dependencies.

- [X] T014 [US1] Convert `validate` in `Makefile` from a prerequisite list into a driver recipe that invokes each stage via `$(MAKE) --no-print-directory`, captures each exit code, and continues past failures. Satisfies FR-001, the requirement that every stage executes regardless of an earlier failure. Each stage remains an independently invokable target; verify `make lint` still works after the change.
- [X] T015 [US1] Replace `fmt` with `fmt-check` in the `validate` stage list in `Makefile`. `fmt-check` already exists at `Makefile:64` and is referenced by nothing, so this is a substitution with no new code. Satisfies FR-004 and SC-007.
- [X] T016 [US1] Add the per-stage summary block to the `validate` driver recipe in `Makefile`, matching the format in `contracts/checker-cli.md`. Each stage prints BLOCKING or ADVISORY alongside its outcome. The dependency-audit stage prints "reported" rather than PASS or FAIL, and the failure count's denominator is blocking stages only. Satisfies FR-002, FR-005, SC-010.
- [X] T017 [US1] Label the dependency-audit stage ADVISORY in the summary and add a comment above the `security` target in `Makefile` recording that it is structurally unable to fail, that promotion to blocking is deferred by FR-005a until the dependency-alert backlog clears, and that a board card tracks it. Do not change the target's behaviour.
- [X] T018 [US1] Add a comment above the `sast` target in `Makefile` recording that the stage is BLOCKING because its second scanner runs with an error flag and genuinely gates (established by a prior feature, preserved per FR-006), and that the first scanner's swallowed exit is pending that scanner's removal, which is tracked by a separate board card and deliberately not changed here.
- [X] T019 [US1] Complete the `.PHONY` declaration at the top of `Makefile` to include `check-test-target-headers`, `check-waitforresponse-race` and `check-iam-patterns`. Pre-existing omission, but T014 makes these names load-bearing sub-make targets: a same-named file at the repository root would silently no-op a stage while the driver recorded a clean exit.
- [X] T020 [US1] Widen the `check-test-target-headers` pattern in `Makefile:49-58` to accept a third sanctioned declaration for tests that target infrastructure rather than either dashboard. Adopt the form already used at `tests/e2e/test_log_visibility.py:1`. The guard must still fail a scanned file carrying no declaration at all, per FR-025. This task plus T021 to T025 constitutes the FR-024 adjudication of all eleven files; their dispositions are recorded in plan.md. Add a comment noting the globs are not recursive and will stop seeing new tests if anyone adds a subdirectory.
- [X] T021 [P] [US1] Add the customer-dashboard declaration to `frontend/tests/e2e/cors-headers.spec.ts`. It is a browser test in the customer suite and is genuinely missing a header.
- [X] T022 [P] [US1] Add the admin-dashboard declaration to `tests/e2e/test_admin_lockdown_preprod.py` and `tests/e2e/test_chaos_lockdown_preprod.py`. Both test admin route lockdown.
- [X] T023 [P] [US1] Add the infrastructure declaration to `tests/e2e/test_cloudfront_sse.py`, `tests/e2e/test_cognito_auth.py`, `tests/e2e/test_function_url_restricted.py` and `tests/e2e/test_waf_protection.py`, naming what each actually targets. **`tests/e2e/test_log_visibility.py` DOES need an edit**, contrary to earlier drafts. Its header reads `# Target: backend Lambda CloudWatch log groups (not either dashboard UI)`, which declares what it is *not* rather than naming the third category. Verified by adversarial review #3: widening the pattern to accept an Infrastructure declaration still leaves all eleven files failing. Rewrite its header to the sanctioned third form while keeping the descriptive detail.
- [X] T024 [US1] Read `tests/e2e/test_cors_404_e2e.py`, `tests/e2e/test_cors_e2e.py` and `tests/e2e/test_cors_prod_headers.py` and assign each the accurate declaration. Preliminary reading suggests the first and third are gateway-level infrastructure and the second is a full-stack auth flow that may be customer-facing. Confirm against the file, do not assume.
- [X] T025 [US1] Verify `check-test-target-headers` exits 0 and that all eleven previously failing files are resolved, satisfying SC-011.
- [X] T026 [US1] Verify the gate does not modify the tree: run `git status --porcelain` and a checksum over all tracked files before and after two consecutive gate runs, confirming both are identical. Checksumming only `src/` and `tests/` would miss the infrastructure tree that the linting stage touches, and FR-004 says any tracked file. Satisfies SC-007.

**Checkpoint**: All seven stages run and report. Header guard green. Tree unmodified.

---

## Phase 4: User Story 2 - A reviewer can tell a violation from a historical record (P1)

**Goal**: The exemption mechanism exists, the adjudication rule is applied to every match, and the
corpus reaches zero unexempted occurrences.

**Independent test**: Add a legacy term to an application source file, confirm the checker fails.
Add one to a documentation file with the sanctioned marker, confirm it passes. Revert both.

- [ ] T027 [US2] Implement inline marker detection in `scripts/check_banned_terms.py`: the token `legacy-term-ok:` on the same line as a Match, case-insensitively, followed by non-empty justification text. Syntax-agnostic substring test, no comment parsing, so it serves Markdown, HTML, Python, YAML, shell and TypeScript identically. A marker with an empty justification does not exempt, per FR-015. Same-line placement satisfies FR-014 (visible at the line it exempts) and the syntax-agnostic substring test satisfies FR-016 (works in Markdown and HTML).
- [ ] T028 [P] [US2] Add tests to `tests/unit/scripts/test_check_banned_terms.py` covering: marker with justification exempts; marker with empty justification does not exempt; marker on a different line from the match does not exempt; marker detection is case-insensitive.
- [ ] T028a [P] [US2] Add a test to `tests/unit/scripts/test_check_banned_terms.py` covering the marker in an **HTML** fixture, not only Markdown. FR-016 requires both, and after T055 rewords the board card no HTML exemption remains anywhere in the repository, so the HTML half would otherwise be asserted and never exercised. Use an HTML comment wrapper on the same line as the term.
- [ ] T029 [US2] Rename the four directories and two files whose names contain a legacy term, using `git mv` so history is preserved. Choose neutral replacements that describe the retirement without naming the framework. Update the exclusion-list entry in `scripts/check_banned_terms.py` that references one of the renamed directories by its old spelling.
- [ ] T030 [US2] Regenerate `.secrets.baseline` after T029 so its stored filename keys reflect the new directory name. Do not hand-edit it. Confirm the three matches it previously contributed are gone, and that no path-scope exemption was needed to achieve it.
- [ ] T031 [US2] Update every reference to the six renamed paths. **The scope is roughly 90 line hits across 24 files, not the four this task originally claimed**, corrected by adversarial review #3. Enumerate with a single search across the tree before editing, then work directory by directory: `specs/1217-*` alone holds about 44 self-references across six files, plus a further eleven pointing at the two renamed archive directories, and the renamed archive directory holds nine self-references. These all sit inside excluded trees so the checker will never catch a missed one, which is precisely why the enumeration must be mechanical rather than from this list.
- [ ] T031a [US2] While updating references, **leave historical command records intact**. Several hits are transcripts of `git mv` invocations that were actually run at the time. Rewriting those falsifies a record of what happened rather than correcting a stale claim. Where a path in such a record is now wrong, annotate rather than rewrite. This is the same distinction the adjudication rule draws between correcting an assertion and preserving a record.
- [ ] T032 [US2] Record in `scripts/check_banned_terms.py` that the sanctioned exemption set is exactly one mechanism, the inline marker, and that a path-scoped exemption mechanism was found unnecessary once the legacy-named paths were renamed. Note that if a generated file ever contains a legacy term in its content, FR-013 must be amended to re-add it, so a future contributor treats that as an amendment rather than an oversight. **FR-017 has no implementing task by design**: it forbids an exemption mechanism that requires editing generated files, and after T029 no generated file contains a legacy term, so it is satisfied by elimination rather than by construction. Record that here so the absent task reads as deliberate.
- [ ] T033 [US2] Scrub the legacy term from the "Primary Dependencies" example at `.specify/templates/plan-template.md:21`. One-line fix for a latent hazard that has escaped twice in 254 generated plans.
- [ ] T034 [P] [US2] Correct the unfilled template placeholder at `specs/1268-cors-404-headers/plan.md:21`, same origin as T033.
- [ ] T035 [US2] Rewrite the four present-tense assertions in the superseded auth-cache-headers spec that claim a retired framework is the application's current primary dependency: `plan.md:13`, `plan.md:79`, `research.md:98`, `spec.md:81`. Name the resolver the dashboard actually uses. These are token-level substitutions where the surrounding sentence stays true. Part of the FR-019 adjudication.
- [ ] T036 [US2] Rewrite the five non-assertive occurrences in the same directory: a section heading, a research question, a general statement of the framework's capabilities, a line inside a fenced code sample, and a research-task list item (`research.md:8`, `:10`, `:12`, `:17`, `plan.md:72`). **These cannot be token-swapped.** Each needs the surrounding sentence to remain coherent and truthful, and the code sample must not be made to look like a verbatim record of something the original research produced. Owner decision 2026-07-30 chose rewriting over exempting these; see spec.md Clarifications.
- [ ] T037 [P] [US2] Add an inline marker with a justification to the matching line in `docs/cleanup/diagram-drift.md:133`. The row records a drift claim sourced from an archived spec and refuted against live code, which is the textbook exemption case. Place the marker inside the final table cell so Markdown table rendering is unaffected, and verify the rendered table is unchanged. This is the only exemption in the feature. Part of the FR-019 adjudication.
- [ ] T038 [US2] Write the adjudication rule (FR-018) into `specs/001-validate-gate-repair/quickstart.md` if not already sufficient, and confirm it distinguishes correction from exemption clearly enough that an independent reader reaches the same disposition on every current match, satisfying SC-009.
- [ ] T039 [US2] Verify the checker reports zero unexempted occurrences, satisfying FR-021 and SC-003, and that every match from the T001 baseline has a recorded disposition, satisfying FR-011 and SC-008. Re-read the disposition table in plan.md against the final repository state and correct any row that remediation changed, satisfying FR-019's requirement that dispositions be recorded, not merely decided.

**Checkpoint**: Corpus clear. One exemption mechanism. Gate can now exit 0.

---

## Phase 5: User Story 4 - The checker cannot be silently bypassed (P2)

**Goal**: Close both structural bypasses and refuse exemptions where none can be legitimate.

**Independent test**: A file containing both an excluded-path string and a legacy term is still
reported. An empty exclusion configuration does not report success.

- [ ] T040 [P] [US4] Add a test to `tests/unit/scripts/test_check_banned_terms.py` constructing a fixture file whose CONTENT contains an excluded-path string on the same line as a legacy term, asserting the violation is still reported. This is SC-005 and the regression guard for FR-007.
- [ ] T041 [P] [US4] Add a test asserting an empty exclusion configuration does not produce a passing result, satisfying SC-006 and FR-009. The Python implementation makes fail-open unreachable rather than guarded, so this test records the property as intended rather than accidental.
- [ ] T042 [P] [US4] Add a test asserting identical results when the same fixture tree is scanned via a relative and an absolute `--root`, satisfying FR-027.
- [ ] T043 [US4] Implement FR-028 in `scripts/check_banned_terms.py`: an inline marker under an application source, infrastructure, or frontend source tree is an error in itself, reported with its own distinct message per `contracts/checker-cli.md`. Reuse the canonical path from T006 so there is one notion of a path. The message must name the marker as the error, not the term, because silently ignoring it would surface as an ordinary violation and lead a contributor to assume the marker was malformed.
- [ ] T044 [P] [US4] Add a test for FR-028 asserting a marker in a source-tree fixture fails with the marker-specific message, satisfying SC-013.
- [ ] T045 [US4] Perform the red-team proof for SC-004: insert a legacy term into an application source file, confirm the checker fails and names the file and line, then revert. With no genuine violation anywhere in the remediated corpus, this insertion is the only available evidence that the checker still detects anything. Record the result in the feature's artifacts. Do not commit the insertion. Satisfies FR-010.

**Checkpoint**: Both bypasses closed, detection proven by insertion rather than assumed.

---

## Phase 6: User Story 3 - The policy actually gates a merge (P2)

**Goal**: Move the policy from voluntary local execution to a check that blocks a merge.

**Independent test**: Open a pull request containing an unexempted legacy term in an application
source file and confirm a required check fails.

- [ ] T046 [US3] Add a step invoking `python3 scripts/check_banned_terms.py` to the `lint` job in `.github/workflows/pr-checks.yml`, following the precedent step at lines 73-87 exactly: `if: always()` so an earlier lint failure does not suppress it, direct invocation rather than through pre-commit so the pre-commit job's skip mechanism cannot reach it, and no install step since the checker is stdlib-only and the job already provides the interpreter. Satisfies FR-022a by joining an already-required job rather than adding a status context.
- [ ] T047 [US3] Add the explanatory comment above the new step in `.github/workflows/pr-checks.yml` recording why a legacy-term scan lives in a job named for linting: `Lint` is a required status context and the pre-commit job is not, so this is the only place the check can block a merge. Without the comment the step looks misfiled and invites a tidy-up that would silently downgrade it to advisory. Include the verification command and date for the required-contexts claim, matching the precedent's style.
- [ ] T048 [US3] Add a pre-commit hook for the checker in `.pre-commit-config.yaml`, mirroring the precedent at lines 206-208. This is deliberately secondary: it gives fast local feedback and is not load-bearing, because that job is not a required context.
- [ ] T049 [US3] Verify the wiring by pushing a branch containing a deliberate unexempted violation and confirming the `Lint` check fails, then removing it. Satisfies FR-022 and User Story 3's acceptance scenario. **Run this BEFORE T048, or the new pre-commit hook blocks the very commit this task needs to make.** The usual bypass is unavailable: project policy forbids it and a global hook hard-denies the flag. If T048 has already landed, use `SKIP=check-banned-terms git commit -S` instead. Delete the branch afterwards so it does not become an orphan.

**Checkpoint**: Policy enforced on the merge path.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T050 Implement `--list-exemptions` in `scripts/check_banned_terms.py` per `contracts/checker-cli.md`: every inline marker with path, line and justification, sorted by kind then path, with a total, exiting 0. Satisfies FR-026.
- [ ] T051 Add an `audit-exemptions` target to `Makefile` invoking the above, placed and named to mirror the existing `audit-pragma` target so it needs no explanation to anyone who has seen that one.
- [ ] T052 [P] Record the resulting exemption count as the SC-012 baseline in `specs/001-validate-gate-repair/plan.md`. Expected to be 1 under the current dispositions, since T029's renames removed the need for path-scope exemptions and T037 is the only inline marker.
- [ ] T053 Delete `scripts/check-banned-terms.sh` and update **all** consumers, which adversarial review #3 measured at roughly eight rather than the four originally listed. Enumerate mechanically with a tree-wide search for the script name, then fix: `specs/1217-*/quickstart.md`, `specs/1217-*/tasks.md`, `specs/1217-*/plan.md` (seven references including a verbatim copy of the Makefile recipe), `specs/1218-*/quickstart.md`, `specs/1218-*/tasks.md`, `specs/1218-*/plan.md`, `specs/002-waitforresponse-lint-guard/spec.md` and `tasks.md`, this feature's own `quickstart.md`, and `Makefile` (the `.PHONY` line and the recipe, though T011a should already have handled the recipe). `docs/cleanup/validator-inventory.md` was checked and has no reference. **Also remove the `"scripts/check-banned-terms.sh"` entry from `CHECKER_SELF_PATHS` in `scripts/check_banned_terms.py`.** That entry exists only because both checkers coexist between T011a and this task; the new checker would otherwise scan the old one's term list and report 8 findings that phase 4 cannot clear, leaving the corpus unable to reach zero. Once the script is gone the entry is dead configuration and misleads the next reader into thinking a shell checker still exists.
- [ ] T054 [P] Document the `make -n` behaviour change in `specs/001-validate-gate-repair/quickstart.md`: GNU Make treats recipe lines containing `$(MAKE)` as recursive and executes them even under dry-run, so `make -n validate` now really runs the stages. Mitigated by T015 removing the mutating format stage, but `make -n` is ordinary reconnaissance and the flip must not be a surprise.
- [ ] T055 [P] Reword board card index 131 in `CLEANUP-BOARD.html` so it describes the legacy terms without reproducing them, and correct its stale match count. Satisfies FR-020. **Board edits are orchestrator-owned**; coordinate rather than committing this inside the feature branch alongside other features' board edits.
- [ ] T056 Close the open validation task in `specs/002-waitforresponse-lint-guard/tasks.md` and propagate the closure to every downstream artifact of that feature, satisfying FR-023 and the project's waterfall rule. **This feature also invalidates two of that feature's factual claims**: its `tasks.md:622-623` documents the old prerequisite ordering and short-circuit behaviour, and its `spec.md:700` quotes the old prerequisite list verbatim. Both describe a gate that will no longer exist. Correct them in the same pass.
- [ ] T057 Run the full gate end to end and confirm it exits 0 with a per-stage summary accounting for all seven stages, satisfying SC-001 as amended, SC-002 and FR-003. Note SC-001's "provisioned" also implies network reachability: the dependency-audit stage queries a remote advisory database and the static-analysis stage downloads its rule set.
- [ ] T058 Run `pytest tests/unit/scripts/test_check_banned_terms.py --cov=scripts.check_banned_terms` and confirm coverage meets the constitution's 80% threshold for new code. Note `make test-unit` uses `--cov=src`, which does not measure `scripts/`, so the bare flag would report the wrong thing.
- [ ] T059 Confirm this feature's own artifacts added zero matches to the corpus, and that the final count reflects only the intended dispositions.

---

## Dependencies

```text
Phase 1 (Setup)
   └─> Phase 2 (Foundational: checker + tests)   BLOCKING for everything below
          ├─> Phase 3 (US1: gate structure + header guard)
          ├─> Phase 4 (US2: exemptions + corpus + renames)
          ├─> Phase 5 (US4: bypass hardening)
          └─> Phase 6 (US3: CI wiring)
                 └─> Phase 7 (Polish)
```

**Cross-story dependency worth stating plainly**: User Story 1's acceptance includes the gate exiting
0, which cannot happen until User Story 2's remediation lands. Phase 3 delivers the observable half
(all stages run, summary prints, header guard green) and Phase 4 delivers the exit code. This is a
genuine ordering constraint, not an artifact of how the phases were drawn.

**Phase 6 should follow Phase 5.** Wiring a checker into a required job makes any defect in it a
repository-wide merge outage, and the checker fails closed. The hardening and its tests must land
before the checker is put in a blocking position.

**Phase 4 internal ordering**: T029 (renames) must precede T030 (baseline regeneration), and T033
should precede T034 so the root cause is fixed before its output is cleaned up.

## Parallel Opportunities

- **Phase 1**: T002, T003, T004 are independent reads and run together after T001.
- **Phase 3**: T021, T022, T023 touch disjoint files and run together. T024 requires reading first.
- **Phase 4**: T034 and T037 are independent of the rename chain. T028 runs alongside T027's tests.
- **Phase 5**: T040, T041, T042, T044 are four independent test additions to the same module; write
  together, but expect one merge point in the file.
- **Phase 7**: T052, T054, T055 are independent.

## Implementation Strategy

**MVP is Phase 1 through Phase 4.** That delivers a gate which runs every stage, reports truthfully,
and exits 0, which is the whole point of the feature. Phases 5 and 6 harden and enforce it.

**Suggested increments**:

1. Phases 1 and 2, landing a tested checker that provably matches the current one. Reviewable alone.
2. Phase 3, landing the gate structure. The summary block becomes visible here.
3. Phase 4, landing remediation. The gate goes green.
4. Phases 5 and 6, landing hardening then enforcement, in that order for the reason above.
5. Phase 7.

**Deliberately not in scope**, each tracked by a board card added 2026-07-30: removal of the first
static-analysis scanner, promotion of the dependency-audit stage to blocking, the non-required status
of the pre-commit job, environment provisioning and a preflight stage, and the constitution drift
audit. Adversarial review grew this feature twice already; these were carded rather than folded in
per the owner's standing instruction to avoid sidelining work in progress.
