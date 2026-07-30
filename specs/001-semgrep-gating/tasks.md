# Tasks: Make the SAST Semgrep Step a Real Gate

**Input**: Design documents from `/specs/001-semgrep-gating/`
**Prerequisites**: plan.md, spec.md (with Clarifications + AR#1), research.md (R1-R7), data-model.md, quickstart.md — all AR#2-amended

**Organization**: Tasks grouped by user story. CRITICAL ORDER CONSTRAINT (FR-006): US3 (baseline disposition) MUST complete before US1's gate flip lands — a gate that fails on its own unmodified tree gets reverted. Phases are sequenced accordingly (US3 before US1 despite both being P1).

**Standing rider (applies to EVERY task)**: RUFF CHURN LANDMINE — after any `make validate`, discard the ~68-file reflow with `git checkout -- src tests` before staging anything. Never `git add -A`. GPG-sign all commits (`git commit -S`). Venv active for all work.

## Phase 1: Setup

- [ ] T001 Install the scanner into the project venv: `source .venv/bin/activate && pip install semgrep==1.172.0`; verify `semgrep --version` → 1.172.0. (Provisioning-file pins land in Phase 2; this unblocks local verification now.)

## Phase 2: Foundational (blocking — both provisioning surfaces pinned identically)

- [ ] T002 [P] Add `semgrep==1.172.0` to `requirements-dev.txt` adjacent to the bandit pin (line 38 area), with a brief comment matching the file's existing style (e.g., "Comprehensive SAST (make sast gate)").
- [ ] T003 [P] Tighten `pyproject.toml` line 55 dev extra from `"semgrep>=1.50.0",` to `"semgrep==1.172.0",  # Feature 001-semgrep-gating: pinned to match requirements-dev.txt` (mirror the bandit pin's comment style on line 54). Do NOT touch `requirements-ci.txt` (FR-001 deliberate exclusion).

## Phase 3: User Story 3 — Baseline disposition (P1, MUST precede gate flip per FR-006)

**Goal**: The 3 measured gate-severity findings are dispositioned so an unmodified tree passes at gate severity.
**Independent test**: `semgrep scan --config auto --error --severity ERROR --severity WARNING src/` exits 0 on the post-change tree (run directly; the Makefile gate is not flipped yet).

- [ ] T004 [P] [US3] In `src/lambdas/analysis/Dockerfile`: add TWO lines immediately ABOVE the `CMD ["handler.lambda_handler"]` line (line 57): a justification comment, then `# nosemgrep: dockerfile.security.missing-user.missing-user`. Justification wording (research R5a, AR#2 F7): managed-base-image Lambda; runtime-environment changes vetoed by image-Lambda crash-loop history (commit 118ab27); platform sandbox is defense-in-depth; sse_streaming's `USER lambda` is a custom-bootstrap image (different execution model). CRITICAL (AR#2 F1): the CMD line itself stays byte-identical — a trailing comment ON a CMD line is folded into the instruction by Docker and corrupts the handler.
- [ ] T005 [P] [US3] Same two-line addition ABOVE the `CMD ["handler.lambda_handler"]` line (line 60) in `src/lambdas/dashboard/Dockerfile`, same justification and same byte-identical-CMD constraint.
- [ ] T006 [P] [US3] In `src/lambdas/analysis/sentiment.py` line 118: change `tar.extractall(path="/tmp")  # nosec B108 B202 - Lambda /tmp` to `tar.extractall(path="/tmp", filter="data")  # nosec B108 B202 - Lambda /tmp` — the nosec comment text stays untouched (bandit-migration card ownership).
- [ ] T007 [US3] Add a unit test to `tests/unit/test_sentiment.py` in the `TestS3ModelDownload` class scoped to traversal-member REJECTION (the uncovered behavior — happy path already covered per AR#2 F2): build a tar.gz in `tmp_path` containing a `../`-escaping member, invoke the real extraction path (the class's autouse fixture already disables the module-level mock). ASSERTION (AR#3 F1 — load-bearing): `_download_model_from_s3` wraps ALL exceptions as `ModelLoadError` (sentiment.py:132-141), so assert `with pytest.raises(ModelLoadError) as exc_info:` then `assert isinstance(exc_info.value.__cause__, tarfile.OutsideDestinationError)` — the `__cause__` check is what discriminates the fixed tree from the unfixed one (asserting the raw tarfile error fails on correct code; asserting ModelLoadError alone passes vacuously on unfixed code, which hits PermissionError → same wrapper). A filesystem-absence check may be added as belt-and-braces but MUST NOT be the sole assertion. Fixed deterministic data (constitution: no `datetime.now()` etc.). Run `pytest tests/unit/test_sentiment.py -v` → all green.
- [ ] T008 [US3] Suppress the residual extractall finding, then verify baseline clean. AR#3 F2 verified the trailofbits rule flags the line even WITH `filter="data"` (its pattern ignores the filter argument), so suppression is the mainline, not a contingency: add a justification comment plus `# nosemgrep: trailofbits.python.tarfile-extractall-traversal.tarfile-extractall-traversal` (full doubled-segment id — the short form verifiably does NOT suppress; AR#3 re-check) on its own line immediately ABOVE `with tarfile.open(tar_path, "r:gz") as tar:` (sentiment.py line 117) — the match STARTS at the `with` line, so a trailing marker on the extractall line does NOT suppress (verified). Justification: extraction hardened with `filter="data"` (raises on traversal/absolute/link members, T007-tested); rule pattern predates the filter argument. Then `semgrep scan --config auto --error --severity ERROR --severity WARNING src/` → exit 0, 0 findings. Also verify `git diff main -- src/lambdas/analysis/Dockerfile src/lambdas/dashboard/Dockerfile` (AR#3 F3: diff against main, not the index) shows ONLY added comment lines (CMD byte-identical).

## Phase 4: User Story 1 — Gate flip (P1)

**Goal**: The sast target's semgrep step runs unconditionally, fails loudly when missing, propagates findings, shows stderr.
**Independent test**: quickstart steps 2-5 (clean pass, plant test, missing-binary fail-fast, no-swallow sweep).

- [ ] T009 [US1] Replace `Makefile` lines 78-83 (the `@if command -v semgrep` skip/swallow block) — KEEPING line 77's `Running Semgrep` heading echo and line 84's trailing `✓ SAST scan complete` echo (AR#2 F5) — with the R3 recipe: a `@command -v semgrep >/dev/null 2>&1 || { echo "$(RED)✗ Semgrep not installed. Install: pip install -r requirements-dev.txt$(NC)"; exit 1; }` guard line, then the bare invocation `semgrep scan --config auto --error --severity ERROR --severity WARNING src/`. Bandit lines 74-75 byte-identical (FR-007).
- [ ] T010 [US1] Clean-tree pass (SC-001): `make sast; echo $?` → exit 0; semgrep's rule/file count summary visible in output; bandit section unchanged. Runtime well under 60s (constitution §10).
- [ ] T011 [US1] Plant test (SC-002, quickstart step 3): plant `src/_sast_plant_test.py` with the `subprocess.call(cmd, shell=True)` pattern (AR#2-verified to trip `python.lang.security.audit.subprocess-shell-true.subprocess-shell-true` as Blocking) → `make sast` nonzero with rule id in output; delete plant → exit 0. NEVER commit the plant.
- [ ] T012 [US1] Missing-binary fail-fast (SC-003, quickstart step 4): shadow-PATH run → nonzero exit, "Semgrep not installed" message with install command, ~10s total (bandit dominates; detection itself instant — AR#2 F4). NOT a skip, NOT "✓ SAST scan complete".
- [ ] T013 [US1] No-swallow sweep (SC-004, quickstart step 5): `sed -n '/Running Semgrep/,/SAST scan complete/p' Makefile` → semgrep lines contain zero `|| true`, `|| echo`, no `2>/dev/null` on the scan invocation, no if/else skip shape; the guard ends in `exit 1`. Additionally assert the flag freeze (FR-008 rules-mode plus the severity-set invariant from data-model): `grep -c -- '--config auto --error --severity ERROR --severity WARNING src/' Makefile` → 1. `git diff main -- Makefile` touches only the semgrep block (FR-007).

## Phase 5: User Story 2 — Fresh provisioning (P2)

**Goal**: Standard provisioning installs the scanner at the pin with zero extra steps.
**Independent test**: quickstart step 1.

- [ ] T014 [US2] Fresh-provision check (SC-005): fresh venv → `pip install -r requirements-dev.txt` → `semgrep --version` = 1.172.0; `grep semgrep requirements-dev.txt pyproject.toml` shows the identical exact pin in both surfaces and no floating spec; confirm `pip install -e .[dev]` in the fresh venv resolves without a version conflict. Remove the fresh venv afterward.

## Phase 6: Polish & Cross-Cutting

- [ ] T015 [P] Suppression justification sweep (SC-006): `grep -rn nosemgrep --include=Dockerfile --include='*.py' --include=Makefile .` → exactly 3 code-surface hits (two Dockerfiles + sentiment.py per AR#3 F2), each with adjacent justification. Constrained grep per AR#2 F3 (unconstrained hits this feature's own docs).
- [ ] T016 [P] Board card portion-close (FR-009): string surgery on `CLEANUP-BOARD.html` CARDS JSON — "Orphaned validators" card: append dated evidence clause, pure ASCII per the surgery caveat (AR#3 F4): "2026-07-29: semgrep portion closed: pinned 1.172.0 both surfaces, make sast gate flipped (hard-fail, no skip/swallow), 3-finding baseline dispositioned; CI provisioning deferred to 1400 family"; rewrite ONLY the semgrep clause of the per-tool next_action (actual live text per AR#2 F6: "Per-tool wire-or-delete decision: pin+install+CI semgrep or drop it from make sast; ..."), leaving LocalStack and mutmut clauses untouched; lane stays `track`. Validate post-edit with the quickstart step 8 raw_decode script. ASCII-substring surgery (em-dash escaping caveat from Feature 1).
- [ ] T017 Full suite + validation: `pytest tests/unit/ -q` green; `make validate` (then IMMEDIATELY `git checkout -- src tests` to discard ruff reflow churn — verify with `git status` that only intended files remain modified); `ruff check src tests` clean on the touched Python files.
- [ ] T018 Run the full quickstart runbook end-to-end (steps 1-8) as final acceptance; record outcomes (exit codes, timings, grep counts) for the completion evidence.

## Dependencies

- T001 → everything (local scanner needed for T008, T010-T013, T018)
- T002, T003 [P with each other] → T014
- T004, T005, T006 [P with each other] → T008; T006 → T007 → T008
- T008 (clean baseline) → T009 (FR-006: gate flips only against clean baseline)
- T009 → T010 → T011 → T012 → T013 (sequential: same file/target under test)
- T013 → Phase 6; T015/T016 [P with each other]; T017 → T018 last

## Implementation Strategy

Single-sitting feature (~10 lines of product change + 1 test + verification). No MVP split: FR-006 couples US3 and US1 into one merge unit; US2 is two pin lines riding along. Execute phases strictly in order; the only parallelism worth taking is within-phase [P] tasks.

## Adversarial Review #3

Independent final-gate review (agent ad305478ae6cca661, 2026-07-29) focused on tasks.md implementability, with empirical verification (live-registry re-scan, repo venv tarfile experiments, live board JSON parse). Initial verdict NOT READY on F1; all findings resolved by the task-text amendments below; re-check confirmed by the same reviewer.

| ID | Severity | Finding | Resolution |
|----|----------|---------|------------|
| F1 | HIGH | T007's assertion could not discriminate: `_download_model_from_s3` wraps ALL exceptions as `ModelLoadError` (sentiment.py:132-141), so asserting the raw `tarfile.OutsideDestinationError` FAILS on correct code, while asserting `ModelLoadError` alone PASSES vacuously on unfixed code (traversal against `/` hits PermissionError → same wrapper; run as root it silently writes outside). Compounded by F2 making this test the ONLY real verification of the fix. | T007 amended: `pytest.raises(ModelLoadError)` + `assert isinstance(exc_info.value.__cause__, tarfile.OutsideDestinationError)` — the `__cause__` check discriminates; filesystem-absence check allowed only as belt-and-braces. |
| F2 | MEDIUM | The extractall suppression "contingency" is empirically the mainline: trailofbits rule flags the line even WITH `filter="data"` (pattern ignores the filter argument), and the marker only suppresses on its own line ABOVE the `with tarfile.open` line (the match starts there; trailing placement verified NOT to suppress). | R5b rewritten as mainline suppression rider with exact placement; T008/T015/quickstart/plan/spec Clarifications synced to 3 expected code-surface suppressions. |
| F3 | LOW | T008's bare `git diff` passes vacuously once T004/T005 are committed. | T008 → `git diff main --`. |
| F4 | LOW | T016's evidence payload contained an em-dash inside the sentence mandating ASCII surgery. | Payload made pure ASCII (colon). |
| F5 | LOW | US3 scenario 2 cited SC-006 as "code-surface search" while SC-006 still said "repo-wide". | SC-006 aligned to code-surface. |
| F6 | INFO | data-model said semgrep block "77-83 pre-change" vs 77-84 elsewhere. | data-model corrected to 77-84 with survivors noted. |
| F7 | INFO | T013's flag grep attributed to FR-008 alone (rules-mode); severity-set freeze lives in the data-model invariant. | T013 label widened. |
| F8 | MEDIUM | (Re-check round) The F2 resolution quoted the SHORT rule id `trailofbits.python.tarfile-extractall-traversal`, which verifiably does NOT suppress — targeted nosemgrep requires an exact match and the registry id doubles the last segment. | T008/R5b corrected to the full id `trailofbits.python.tarfile-extractall-traversal.tarfile-extractall-traversal` (empirically verified suppressing); data-model baseline row now names the rider explicitly. |

Verified-OK (held under attack): Makefile line map and both sed anchors (survive T009, sweep non-vacuous); T013 flag-grep count 1 pre- and post-change (discriminating); T002/T003 executable as written (line refs exact, comment style available); Dockerfile CMD lines and line-above suppression re-verified against today's registry; baseline re-measured TODAY — same 3 findings, no registry drift since AR#1; `OutsideDestinationError` exists and fires for simple and nested traversal members; TestS3ModelDownload autouse fixture matches T007's description with `ModelLoadError` assertion precedent at test_sentiment.py:492; board card JSON matches R6 verbatim and the parse script runs as-is; no [P] same-file collisions; T008 correctly runs semgrep directly pre-flip; SC-003 bandit carve-out consistent across all artifacts.

**Gate: 0 CRITICAL, 0 HIGH remaining. Reviewer re-check (same agent, second round) confirmed all resolutions and caught F8; after the F8 copy-paste fix the reviewer's verdict is CONFIRMED READY FOR IMPLEMENTATION, no further re-check required.**
