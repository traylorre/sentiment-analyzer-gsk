# Feature Specification: Remove tfsec from the Security Validation Chain

**Feature Branch**: `001-tfsec-removal`
**Created**: 2026-07-29
**Status**: Draft
**Input**: User description: "Remove tfsec from the Makefile security target; Trivy/Checkov cover IaC scanning. Sweep stale tfsec references in living docs."

## Context

tfsec is a deprecated Terraform security scanner (its maintainers folded it into Trivy; it never gained Terraform 1.5 `check`-block support). This repository already removed it from pre-commit in favor of a local Trivy hook. One invocation survives in the local security validation chain, and it is doubly decorative: it is skipped silently when the tool is not installed, and when it does run it cannot fail the chain on findings. Three living documents still describe tfsec as an active automated check (contributing guide, project design document, and the governance constitution), which misstates the project's real security posture to contributors and reviewers.

This feature removes the dead invocation and corrects the two documents it can correct directly. The constitution has its own amendment process; its stale claim is recorded here as a follow-up, not silently exempted. Other permanently-green steps in the chain (dependency audit, Python SAST) are known and owned by sibling features — this feature removes exactly one dead step and claims no more than that.

## Clarifications

### Session 2026-07-29 (battleplan autonomous mode — self-answered from repo evidence)

- Q: FR-007 says the "fix-lane card" moves to done, but on this branch what lane is the tfsec card actually in? → A: `track` lane, titled "tfsec orphaned and deprecated — cannot run anywhere" (verified by parsing CLEANUP-BOARD.html CARDS array on this branch). The fix-lane promotion exists only on the unmerged `001-role-derivation-canonical` branch (commit 25f444c). FR-007 reworded to name the card by title, not lane; the future rebase of that branch will hit a board conflict that resolves in favor of `done` (flagged for Phase 2 merge-order guidance).
- Q: What exact replacement wording does SPEC.md line 479 get (it also names semgrep, which stays accurate)? → A: Replace only the tfsec clause: "Run security checks: Trivy/Checkov (IaC), `semgrep` or other SAST for code, dependency checks." — semgrep and dependency-check clauses retained verbatim.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developer runs the security validation chain (Priority: P1)

A developer runs the project's local security validation (directly or via the full validation suite). The tfsec step — which was silently skipped on machines without the binary and could not fail on findings where it did run — no longer appears. The chain's remaining steps behave exactly as before; no step's outcome changes.

**Why this priority**: A scanner that prints output but cannot fail builds false confidence, which is worse than not running it at all. Removing this one dead step is the feature's core value; making the *rest* of the chain honest is sibling features' work (SAST gating) and follow-up work (dependency audit), not this feature's claim.

**Independent Test**: Run the security validation target on a machine with tfsec installed and on one without it. Output is identical in both cases and contains no tfsec invocation.

**Acceptance Scenarios**:

1. **Given** a machine with tfsec installed, **When** the developer runs the security validation target, **Then** tfsec is not executed and does not appear in output.
2. **Given** a machine without tfsec installed, **When** the developer runs the security validation target, **Then** the output is identical to the with-tfsec case (no skip message, no behavioral difference).
3. **Given** the full validation suite, **When** it is run end to end, **Then** it completes with the same pass/fail result as before this change on an unmodified codebase (removal changes no outcomes, because the removed step could not fail on findings).

---

### User Story 2 - Contributor reads the project's security documentation (Priority: P2)

A new contributor reads the contributing guide and project design documents to understand which security checks their PR must pass. The documents name only checks that exist. The contributor does not install or configure tfsec, and does not expect a tfsec gate that will never come.

**Why this priority**: Stale documentation misdirects contributor effort and misstates the security posture to anyone auditing it, but it does not change runtime behavior.

**Independent Test**: Search all living (non-archived) project documents for tfsec; every remaining mention is either historical context (explaining what replaced it) or lives in archived material.

**Acceptance Scenarios**:

1. **Given** the contributing guide, **When** a contributor reads the automated-checks list, **Then** the IaC security scanning entry names the scanners that actually cover IaC (Trivy, Checkov), not tfsec.
2. **Given** the project design document's CI responsibilities section, **When** it names security checks, **Then** tfsec is not listed as an active or planned check.
3. **Given** archived specs and historical review documents, **When** this feature completes, **Then** those files are unchanged (history is not rewritten).

---

### Edge Cases

- A developer's muscle memory or personal scripts invoke tfsec directly: out of scope — the tool remains installable and runnable manually; this feature only removes it from the project's validation chain and docs.
- The comment in the pre-commit configuration explaining *why* tfsec was removed there: retained — it is accurate historical rationale, not a claim that tfsec runs.
- Future reintroduction of a dedicated Terraform scanner: unaffected — Trivy hook and Checkov hook remain in place and are the designated IaC scanners.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The local security validation target MUST NOT invoke tfsec, reference the tfsec binary, or condition any behavior on tfsec's presence.
- **FR-002**: The security validation target's observable output MUST be identical whether or not tfsec is installed on the machine.
- **FR-003**: The contributing guide's automated-checks list MUST name the actual IaC scanners in use instead of tfsec, and MUST be honest about their gating status: Checkov (gating in CI) and Trivy (report-only until its exit-code flip lands via the validator-gating feature's follow-up). It MUST NOT present a report-only scanner as a must-pass gate.
- **FR-004**: The project design document's CI security-checks description MUST NOT name tfsec as an active or planned check.
- **FR-005**: Archived documents, historical reviews, and the governance constitution MUST remain byte-identical (the constitution has its own amendment process and is explicitly out of scope).
- **FR-006**: The removal MUST NOT alter the behavior of any other step in the security or validation chain (pip-audit, SAST, lint, format steps are untouched by this feature).
- **FR-007**: The cleanup board card titled "tfsec orphaned and deprecated — cannot run anywhere" (in the `track` lane on this branch) MUST move to the `done` lane with completion evidence appended, as part of feature completion. Two adjacent cards carry present-tense tfsec claims this feature falsifies and MUST be corrected with dated evidence appends (not rewrites): the "No Terraform semantic validation on PRs" card's undated "Makefile:70 still gates on deprecated tfsec" clause, and the "MASTER: Terraform & infra" roll-up's open tfsec child. Dated verification text on board cards is audit trail and is exempt from the stale-reference sweep.

### Key Entities

- **Security validation chain**: The ordered set of locally runnable security checks a developer invokes before pushing; this feature shrinks it by one permanently-green step.
- **Living documents**: Contributor-facing documents that describe current process (contributing guide, project design document). Distinct from archived specs and dated review records, which are historical and immutable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A repository-wide search for tfsec returns zero matches that describe tfsec as an active check, excluding four allowed remainder classes: (a) archives and dated review/audit records, (b) historical rationale comments (e.g., the pre-commit removal comment), (c) other specs' scope notes, and (d) the governance constitution, which is amended separately and tracked as a follow-up of this feature.
- **SC-002**: The security validation target produces identical output on machines with and without tfsec installed (verified by diffing captured output from both states).
- **SC-003**: The full validation suite's pass/fail outcome on an unmodified codebase is unchanged by this feature (before/after runs agree — the removed step could not fail on findings, and removal eliminates its only residual failure mode, a runtime crash of the tool itself).
- **SC-004**: A contributor reading the contributing guide can list the project's IaC scanners correctly (Trivy, Checkov) without encountering tfsec.

## Assumptions

- The dated Gemini review record (`docs/reviews/gemini-2026-07-29-verdicts.md`) and the validator inventory under `docs/cleanup-pristine/` are historical/audit records, not living process docs; they already describe the tfsec drift accurately and are left unchanged.
- tfsec remains installed at the user level on some machines; uninstalling it from developer machines is out of scope.
- No CI workflow invokes the security validation target today, so this change cannot affect CI outcomes; it is a local-honesty fix.
- After removal, the local security validation target contains no IaC scanning step by design: IaC coverage lives in the pre-commit Trivy and Checkov hooks (and Checkov gates in CI). Adding a gating IaC invocation back into the local target is deferred to the validator-gating feature's follow-up, not lost.

## Follow-ups (out of scope, recorded so they have an owner)

- **Constitution amendment**: `.specify/memory/constitution.md` line 68 claims GitHub Actions runs `tfsec`/`checkov` and `tflint`; no workflow runs tfsec or tflint. Needs a constitution amendment via its own process. Surfaced to the owner in this battleplan's Phase 2 summary.
- **Trivy exit-code flip**: the local Trivy hook runs report-only (`--exit-code 0`); flipping it to gate is owned by the validator-gating feature (1400) follow-up.
- **CONTRIBUTING.md neighbor inaccuracies**: the same automated-checks list claims GitHub Actions runs `terraform validate` (no workflow does; only Makefile `lint`). This feature corrects only the tfsec entry; US2's "docs name only checks that exist" promise applies to the edited line, not the whole list. Full list reconciliation belongs to the 1400 family.

## Adversarial Review #1

Independent hostile review (agent ad41995297d58867f, 2026-07-29) verified every repo-state claim against live files and returned 1 HIGH, 4 MEDIUM, 3 LOW findings. All resolved by spec edits below; no implementation-direction errors found.

| ID | Severity | Finding | Resolution |
|----|----------|---------|------------|
| F1 | HIGH | SC-001 contradicted FR-005: constitution.md:68 describes tfsec as active, FR-005 freezes it, so the repo-wide search could never pass. "Two living documents" was also an undercount (three). | SC-001 rewritten with four explicit allowed-remainder classes including a constitution carve-out; Context corrected to three documents; constitution amendment recorded in new Follow-ups section. |
| F2 | MEDIUM | Constitution's false claim (no workflow runs tfsec or tflint) was exempted with no remediation path. | Follow-ups section names it and routes it to the owner via Phase 2 summary. |
| F3 | MEDIUM | US1/Context overpromised a fully honest chain while FR-006 forbids touching pip-audit/bandit/semgrep swallows. | Context and US1 rewritten to claim exactly one dead-step removal; sibling/follow-up ownership named. |
| F4 | MEDIUM | FR-003 risked minting a new lie: listing Trivy as a must-pass gate while its hook runs `--exit-code 0`. | FR-003 now requires gating-status honesty: Checkov (gating), Trivy (report-only pending 1400 follow-up). |
| F5 | MEDIUM | CLEANUP-BOARD.html (living, root) has present-tense tfsec cards; spec had no classification rule. | FR-007 added: card moves to done lane at completion; dated card text classed as audit trail, exempt from sweep. |
| F6 | LOW | "Could never fail" overstated — a tfsec runtime crash exits nonzero inside the compound. | SC-003 parenthetical reworded: could not fail on findings; removal eliminates the crash mode too. |
| F7 | LOW | SC-001 buckets didn't cover other specs' scope notes (1400 spec line 105). | Added remainder class (c). |
| F8 | LOW | Post-change `make security` holds no IaC step; local/CI parity comment gap widens silently. | Assumption added stating this is by design with coverage location and deferral named. |

Verified-OK (held under attack): Makefile:70 is the sole living executable tfsec surface; no workflow, script, or install path depends on tfsec; skip-silently and soft-fail claims accurate; CONTRIBUTING.md:309 and SPEC.md:479 confirmed as the two directly-correctable references; historical docs already record the drift accurately.

**Gate: 0 CRITICAL, 0 HIGH remaining.**
