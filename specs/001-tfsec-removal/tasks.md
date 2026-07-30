# Tasks: Remove tfsec from the Security Validation Chain

**Input**: Design documents from `/specs/001-tfsec-removal/`
**Prerequisites**: plan.md (+ AR#2 appendix), spec.md (+ AR#1, Clarifications), research.md, data-model.md, quickstart.md

**Organization**: Two user stories from spec.md — US1 (P1, validation chain) and US2 (P2, documentation). Tests not requested; verification is behavioral per plan.md Verification Design.

## Phase 1: Setup

- [ ] T001 Activate venv (`source .venv/bin/activate`), confirm branch `001-tfsec-removal`, confirm expected tree state (`git status --short` shows `M CLAUDE.md` from the speckit agent-context update plus this feature's spec artifacts, nothing else)
- [ ] T002 Capture pre-change baseline: run `make validate; echo $?` from the base state and record the exit code for SC-003 comparison (plan.md Verification Design #2). **RUFF-CHURN RIDER (applies here and to T006/T014)**: `make validate`'s `fmt` step runs venv ruff 0.14.11 in write mode and reflows ~68 files that CI's pinned ruff 0.8.4 rejects; after EVERY `make validate` run, discard formatter churn with `git checkout -- src tests` before proceeding. Never commit reflowed src/tests files in this feature.

## Phase 2: Foundational

(none — no blocking prerequisites; the feature is four independent edits)

## Phase 3: User Story 1 — Developer runs the security validation chain (P1)

**Goal**: `make security` contains no tfsec invocation; output identical regardless of tfsec presence; no other step's behavior changes.

**Independent test**: quickstart.md SC-002 section — capture `make security` with tfsec on PATH and with `~/.local/bin` filtered out; diff must be empty and contain no tfsec output.

- [ ] T003 [US1] Delete the tfsec line from the `security` target in Makefile (currently line 70: `@if command -v tfsec &>/dev/null && [ -d "$(TF_DIR)" ]; then tfsec $(TF_DIR) --soft-fail; fi`); leave the pip-audit line and the advisory echo untouched (FR-001, FR-006)
- [ ] T004 [US1] Update the `sast`/`security` help annotation only if it names tfsec (verified: it does not — `security: ## Run security scanners` stays; confirm no other Makefile line references tfsec via `grep -n tfsec Makefile` returning zero hits) (FR-001)
- [ ] T005 [US1] Verify SC-002 per quickstart.md: `S=$(mktemp -d)`; capture `make security` twice (normal PATH; PATH with `$HOME/.local/bin` entries filtered); `diff` must be empty (FR-002)
- [ ] T006 [US1] Verify SC-003: run `make validate; echo $?` post-change; exit code must equal T002 baseline (FR-006)

## Phase 4: User Story 2 — Contributor reads the project's security documentation (P2)

**Goal**: Living docs name only real scanners with honest gating status; archives and constitution byte-identical.

**Independent test**: quickstart.md SC-001 sweep + FR-003 positive assertions + FR-005 freeze check.

- [ ] T007 [P] [US2] Edit CONTRIBUTING.md line 309: replace `3. Security scanning (tfsec, checkov)` with `3. Security scanning: Checkov (gating), Trivy (report-only pending validator-gating follow-up)` (FR-003)
- [ ] T008 [P] [US2] Edit SPEC.md line 479: replace `Run security checks: \`tfsec\` (Terraform), \`semgrep\` or other SAST for code, dependency checks.` with `Run security checks: Trivy/Checkov (IaC), \`semgrep\` or other SAST for code, dependency checks.` (FR-004, Clarification Q2)
- [ ] T009 [P] [US2] Update CLEANUP-BOARD.html CARDS array (FR-007, Clarification Q1). **Format warning**: the CARDS array is a single minified line using `—` escapes — match cards by ASCII substring (e.g. `tfsec orphaned and deprecated`), never by em-dash literal; append via string surgery, do NOT re-serialize the array (T013's `raw_decode` backstops JSON validity). Three edits, appends only, no rewrites: (a) card titled `tfsec orphaned and deprecated — cannot run anywhere` → `lane: "done"`, append evidence clause `|| [2026-07-29 001-tfsec-removal] FIXED: Makefile tfsec line deleted; CONTRIBUTING.md/SPEC.md corrected; refuter-verified` (no SHA — a later board reconcile adds it post-merge); (b) card titled `No Terraform semantic validation on PRs: tflint absent; make-only terraform validate; plan is post-merge` → append evidence clause `|| [2026-07-29 001-tfsec-removal] Side-drift resolved: Makefile:70 tfsec line deleted`; (c) card titled `MASTER: Terraform & infra` → append evidence clause `|| [2026-07-29 001-tfsec-removal] tfsec child resolved (see tfsec-orphaned card, done lane)`
- [ ] T010 [US2] Verify SC-001 sweep per quickstart.md (basename `--exclude-dir` form); classify every remaining hit into the allowed remainder classes; zero hits may describe tfsec as an active check (FR-001, FR-003, FR-004)
- [ ] T011 [US2] Verify FR-003/SC-004 positive assertions per quickstart.md (`grep -n "Checkov" CONTRIBUTING.md`, `grep -n "Trivy/Checkov" SPEC.md`)
- [ ] T012 [US2] Verify FR-005 freeze: `git diff --stat main -- docs/archived-specs docs/reviews docs/cleanup-pristine .specify/memory` is empty
- [ ] T013 [US2] Verify FR-007 board assertion per quickstart.md python snippet (lane == done, dated evidence clause present)

## Phase 5: Polish & Commit

- [ ] T014 Run full pre-push validation: `make validate` green (or same-as-baseline), then apply the T002 ruff-churn rider (`git checkout -- src tests`); pre-commit hooks pass on staged files
- [ ] T015 GPG-signed commit: stage ONLY the named paths — `git add Makefile CONTRIBUTING.md SPEC.md CLEANUP-BOARD.html CLAUDE.md specs/001-tfsec-removal/` (never `git add -A`; see T002 rider) — then `git commit -S` with message `fix(toolchain): remove dead tfsec invocation from make security; correct living docs` (no SHA backfill — see T009)

## Dependencies

- T003 → T005, T006 (verify after edit)
- T007/T008/T009 are [P] (different files, no interdependency)
- T010-T013 after T007-T009
- T014-T015 last; T002 before T003 (baseline before change)

## Parallel Example

T007, T008, T009 may run concurrently (three different files). Everything else is sequential single-developer flow.

## Implementation Strategy

MVP = Phase 3 (US1) alone: the Makefile deletion with SC-002/SC-003 verification is independently shippable. Phase 4 completes the honesty sweep. Estimated total diff ≈ 4 edited lines + board JSON appends.

## Adversarial Review #3

Final implementation-readiness gate (agent a0dde8bf48c3685d8, 2026-07-29). 1 HIGH, 2 MEDIUM, 3 LOW, 1 INFO — all resolved by task edits above before this gate statement.

| ID | Severity | Finding | Resolution |
|----|----------|---------|------------|
| AR3-F1 | HIGH | `make validate` (T002/T006/T014) mutates the tree: venv ruff 0.14.11 reflows ~68 files CI's 0.8.4 rejects; the churn gotcha lived only in session memory, invisible to an implementing agent. | Ruff-churn rider added to T002 (applies to T006/T014): `git checkout -- src tests` after every validate run; T015 rewritten to stage only named paths, `git add -A` banned. |
| AR3-F2 | MEDIUM | T009 card (b) title was truncated vs live board; append text for cards (b)/(c) was unspecified judgment. | T009 now quotes full live titles and exact append strings for all three cards. |
| AR3-F3 | MEDIUM | Cards (b)/(c) appends had no executable verification — skipping them passed silently. | quickstart FR-007 snippet extended with asserts for all three cards. |
| AR3-F4 | LOW | T001 clean-tree criterion false (M CLAUDE.md exists from agent-context update); T015 omitted CLAUDE.md. | T001 expected-status corrected; CLAUDE.md added to T015 stage list. |
| AR3-F5 | LOW | SC-002 post-change diff is near-tautological; pip-audit live-DB noise could cause spurious diff. | Accepted as regression guard (plan already says so); rerun-on-diff note added to quickstart. |
| AR3-F6 | LOW | CARDS array is minified single-line JSON with `—` escapes; em-dash exact-match edits fail. | Format warning added to T009: ASCII-substring matching, string surgery only, T013 raw_decode backstop. |
| AR3-F7 | INFO | T004 is a self-answering guard; T012 freeze diff correctly non-vacuous. | No change. |

**Highest-risk task**: T009 — surgical appends inside a 75KB single-line JSON blob, two of three previously unverified (now all three asserted by T013's extended snippet).

**Most likely rework source**: ruff formatter churn from `make validate` — neutralized by the T002 rider and T015 explicit stage list.

**Spot-checks (3/3 CONFIRMED)**: board lane/title byte-exact; Makefile:70 sole executable tfsec surface with byte-exact T003 old-string; CONTRIBUTING wording accuracy (checkov 3.2.508 gates in CI pre-commit job, trivy `--exit-code 0` report-only).

**3am test**: fresh puller sees no breakage — `make security` becomes pip-audit + echo (no binary deps changed); `make validate` structurally unchanged (ruff skew pre-exists, owned by the ruff-bump feature); pre-commit untouched.

**Gate: READY FOR IMPLEMENTATION** (0 CRITICAL, 0 HIGH remaining).
