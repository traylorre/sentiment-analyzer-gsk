# Implementation Plan: Remove tfsec from the Security Validation Chain

**Branch**: `001-tfsec-removal` | **Date**: 2026-07-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-tfsec-removal/spec.md`

## Summary

Delete the dead tfsec invocation from the Makefile `security` target and correct the two directly-correctable living documents (CONTRIBUTING.md, SPEC.md) that still present tfsec as an active check. Trivy (pre-commit, report-only pending 1400 follow-up) and Checkov (pre-commit + CI, gating) are the designated IaC scanners. Constitution's stale claim is deferred to its own amendment process and recorded as a follow-up. Verification is behavioral: `make security` output must be byte-identical with and without tfsec on PATH, and `make validate`'s outcome on a clean tree must be unchanged.

## Technical Context

**Language/Version**: GNU Make (Makefile recipe edit), Markdown (two doc edits), HTML (board card lane move). No Python code.
**Primary Dependencies**: None added or removed. tfsec binary itself is untouched (remains at user level on some machines).
**Storage**: N/A
**Testing**: Behavioral diff of captured `make security` output (tfsec on PATH vs shadowed via PATH manipulation); before/after `make validate` on clean tree; repo-wide grep against SC-001's four remainder classes.
**Target Platform**: Developer workstations (Linux/WSL2); no CI workflow invokes `make security` today (verified AR#1).
**Project Type**: Single project, tooling/docs-only change.
**Performance Goals**: N/A (removal strictly reduces work performed).
**Constraints**: FR-005 byte-identical freeze on archives/constitution; FR-006 no behavior change to any other validation step; GPG-signed commits; no new AWS resources (trivially satisfied).
**Scale/Scope**: 1 Makefile line deleted, 1 line edited in CONTRIBUTING.md, 1 line edited in SPEC.md, 1 board card lane move. ~4 lines total.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Justification |
|------|--------|---------------|
| Unit tests accompany all implementation code | PASS (N/A) | No implementation code — a Makefile recipe line deletion and doc edits. Behavioral verification (output diff, before/after validate) substitutes; there is no unit-testable surface. |
| External dependencies mocked in tests | PASS (N/A) | No tests touch external services. |
| Pre-push requirements (ruff lint/format, GPG-signed, feature branch) | PASS | Branch `001-tfsec-removal`; commits GPG-signed; no Python files touched so lint/format are no-ops but still run via `make validate`. |
| Local SAST before push | PASS | `make sast` unaffected by this feature (FR-006) and runs as part of pre-push validation. |
| Tech debt tracking | PASS | This feature *retires* recorded drift (validator-inventory.md:37 recommends exactly this deletion). No new debt introduced. Constitution follow-up recorded in spec Follow-ups section. |
| No new AWS resources | PASS | Nothing infrastructural. |

**Post-design re-check (after Phase 1)**: unchanged — PASS on all gates. No Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-tfsec-removal/
├── spec.md              # Stage 1 + AR#1 appendix
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (minimal — no data entities)
├── quickstart.md        # Phase 1 output (verification runbook)
├── checklists/
│   └── requirements.md  # Spec quality checklist (passed)
└── tasks.md             # Phase 2 output (/speckit.tasks — not yet created)
```

### Source Code (repository root)

```text
Makefile                 # security target: delete tfsec line (currently line 70)
CONTRIBUTING.md          # line 309: automated-checks list entry
SPEC.md                  # line 479: CI security-checks list
CLEANUP-BOARD.html       # tfsec card (track lane, matched by title) → done lane (at completion)
```

**Structure Decision**: No source tree changes. Four existing files edited in place; no files created or deleted outside `specs/001-tfsec-removal/`.

## Verification Design

1. **SC-002 (output identity)**: capture `make security 2>&1` twice — once normally (tfsec at `~/.local/bin/tfsec`), once with tfsec shadowed (`PATH` filtered or a temp dir earlier in PATH containing no tfsec). `diff` the captures; must be empty. Run on the post-change tree. (On the pre-change tree they differ only if `infrastructure/terraform` exists and tfsec is installed — that asymmetry is the bug being deleted.)
2. **SC-003 (no outcome change)**: `make validate; echo $?` before and after the change on an otherwise clean tree; exit codes must match. Note: `make validate` currently fails at `fmt`/`lint` only if the tree is dirty in ways unrelated to this feature; run both invocations from the same base commit state.
3. **SC-001 (reference sweep)**: `grep -rn tfsec --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules --exclude-dir=archived-specs --exclude-dir=reviews --exclude-dir=cleanup-pristine .` (basename form — GNU grep's `--exclude-dir` does not match path-style args). Remaining hits must each fall into remainder classes (a) any archive hit leaking through on other grep implementations, (b) historical rationale (`.pre-commit-config.yaml` comment), (c) other specs' scope notes (1400 spec, this spec's own artifacts, project CLAUDE.md auto-generated tech entries), or (d) constitution.
4. **FR-005 (freeze)**: `git diff --stat main -- docs/archived-specs docs/reviews docs/cleanup-pristine .specify/memory` must be empty (diff against `main`, not the worktree — post-commit the worktree diff passes vacuously).
5. **FR-007 (board)**: parse the board's CARDS array; the card titled "tfsec orphaned and deprecated — cannot run anywhere" must have `lane == "done"` with a dated completion clause appended to its evidence; the "No Terraform semantic validation on PRs" card's undated "Makefile:70 still gates on deprecated tfsec" clause must gain a dated correction; the "MASTER: Terraform & infra" roll-up must mark the tfsec child resolved.

## Complexity Tracking

No constitution violations; table intentionally empty.

## Adversarial Review #2

Independent cross-artifact review (agent aa27e7aa796abe57a, 2026-07-29) after the Clarifications session. Verdict: clarifications introduced no contradictions into spec.md; all drift was in plan.md (written pre-clarification) plus verification-mechanics gaps. 0 CRITICAL, 0 HIGH; 6 MEDIUM, 3 LOW — all resolved.

### Drift findings (Stage 1 → now)

| ID | Severity | Finding | Resolution |
|----|----------|---------|------------|
| F-1 | MEDIUM | plan.md still said "fix-lane card"; clarified fact is the card sits in `track` on this branch. | plan.md Source Code entry corrected to lane-neutral, title-matched wording. |
| F-2 | MEDIUM | FR-007 had no verification path in plan or quickstart. | Verification Design step 5 added (CARDS parse assertion); quickstart FR-007 section added. |
| F-3 | MEDIUM | FR-003's positive wording and SC-004 had no verification command — the sweep only proves absence. | quickstart positive-assertion section added (Checkov gating / Trivy report-only qualifiers). |
| F-4 | MEDIUM | plan's sweep used path-style `--exclude-dir` args, which GNU grep ignores (works only under the owner's ugrep wrapper); archive hits would leak and fail a literal verifier. | Command rewritten in basename form; remainder class (a) added for cross-grep tolerance. |
| F-5 | MEDIUM | quickstart's scratchpad glob assignment never expands; SC-002 script failed as written. | `S=$(mktemp -d)`. |
| F-6 | MEDIUM | Two more board cards carry present-tense tfsec claims the feature falsifies (tflint card's undated side-drift clause; MASTER roll-up child); FR-007 covered only one card. | FR-007 widened: dated evidence appends required on both adjacent cards. |
| F-7 | LOW | plan's freeze check diffed the worktree (vacuous post-commit). | Diff pinned against `main`. |
| F-8 | LOW | Sweep hit-classes missed this branch's own CLAUDE.md entries and untracked session files. | quickstart allowed-hit comment extended. |
| F-9 | LOW | CONTRIBUTING.md neighbor entry (`terraform validate` as a GHA check) is also false; out of this feature's scope but US2 could be over-read. | Spec Follow-ups note added scoping US2's promise to the edited line. |

### Cross-artifact consistency

Verified-OK under attack: clarified lane fact matches live CARDS parse byte-for-byte; Makefile:70 text and TF_DIR exact; SPEC.md:479 splice retains semgrep/dependency clauses verbatim; promised CONTRIBUTING wording is factually accurate per pr-checks.yml pre-commit job (checkov gates, trivy `--exit-code 0`); constitution follow-up claim accurate (zero tflint/tfsec hits in workflows); PATH-shadow approach sound (`which -a tfsec` → single user-level binary); FR→verification coverage now complete for FR-001..FR-007 and SC-001..SC-004 with no orphan verification steps.

**Gate: 0 CRITICAL, 0 HIGH remaining.**
