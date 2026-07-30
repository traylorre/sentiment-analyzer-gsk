# Feature Specification: Make the SAST Semgrep Step a Real Gate

**Feature Branch**: `001-semgrep-gating`
**Created**: 2026-07-29
**Status**: Draft
**Input**: User description: "Make the semgrep step of make sast a real gate: hard-fail on findings, no skip-if-missing, no output swallows; pin semgrep in dev requirements."

## Context

The project's local SAST step advertises comprehensive scanning, but its Semgrep half is triple-neutered: it is skipped silently when the tool is absent — and the primary documented provisioning path (the pinned development requirements) omits it, so machines provisioned that way have always skipped it. (A secondary provisioning path, the packaging dev extra, declares it at a floating minimum version; a machine provisioned that way ran it with findings swallowed — differently broken, same net silence.), its findings are swallowed so the step always reports success, and its error output is discarded. The project's own validator-gating audit (feature 1400) classified this step as orphaned and left reviving it as an explicit separate decision. This feature is that decision.

The end state: Semgrep is a pinned development dependency, the SAST target invokes it unconditionally, a missing binary is a loud error, findings at the gate severity fail the target with a nonzero exit, and error output is visible.

The gate flips on only against a clean baseline. That baseline is now measured (adversarial review #1, 2026-07-29, scanner 1.172.0 in a throwaway environment): exactly 3 gate-severity findings on the current tree — two missing-user findings on the analysis and dashboard container definitions, one archive-extraction traversal finding in the analysis code. All three have cheap dispositions; baseline cleanup is a closed three-item worklist, not an open-ended project.

One structural trade-off is accepted knowingly: the auto-config rules mode (kept per the card's scope) fetches rule content from the vendor registry on every run. Rule content therefore floats server-side — the engine version is pinned, the rules are not. This buys zero-maintenance rule freshness at the cost of occasional new findings appearing without any repo change.

## Clarifications

### Session 2026-07-29

- Q: What exact severity threshold does the gate use? → A: Today's invocation unchanged (`--error --severity ERROR --severity WARNING`); confirmed against the measured baseline (3 findings, all ERROR) — narrowing to ERROR-only would silently weaken the advertised gate.
- Q: Is a metrics-off flag applied? → A: No — verified empirically incompatible with auto-config (semgrep 1.172.0 exits 2: "Cannot create auto config when metrics are off"). The telemetry acceptance in Assumptions is final.
- Q: Which version is pinned? → A: `semgrep==1.172.0` (the version the baseline was measured with) in both provisioning surfaces.
- Q: How is each baseline finding dispositioned? → A: The two Dockerfile missing-user findings are suppressed — marker on its own line immediately ABOVE each CMD (a trailing comment on a CMD line is folded into the instruction by Docker and corrupts it; the CMD lines stay byte-identical) — with adjacent justification led by the verifiable rationale: image-Lambda crash-loop history at 118ab27 vetoes runtime-environment changes, the Lambda platform sandbox stands as defense-in-depth, and the sse_streaming USER precedent is a custom-bootstrap image with a different execution model. The tarfile extractall finding is fixed for real with `filter="data"` (Python 3.13) plus a new unit test scoped to traversal-member rejection (the happy-path extraction is already covered by TestS3ModelDownload); because the scanner's rule ignores the filter argument (verified), the fix carries a nosemgrep rider with justification above the `with` line — three code-surface suppressions total; the existing `# nosec` comment is untouched (bandit-migration ownership).
- Q: What runtime bound applies to the gated target? → A: The constitution §10 ceiling (`make sast` < 60 seconds) is inherited, not restated; measured ~15-20s with registry fetch dominating.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developer runs SAST and findings block (Priority: P1)

A developer runs the local SAST validation (directly or via the full validation suite). The Semgrep step runs every time, on every machine provisioned from the project's development dependencies. If Semgrep reports a finding at the gate severity, the target fails with a nonzero exit and the finding is visible in output. If the tool is missing, the target fails loudly instead of pretending to pass.

**Why this priority**: This is the entire card: converting a decorative step into a gate. The repo's security posture claims local SAST detection before push; today that claim is false for the Semgrep half.

**Independent Test**: Introduce a file containing a known gate-severity pattern, run the SAST target, observe nonzero exit and the finding in output; remove the file, observe the target passes again.

**Acceptance Scenarios**:

1. **Given** a provisioned dev environment and a clean codebase, **When** the developer runs the SAST target, **Then** Semgrep executes and the target exits zero.
2. **Given** a file containing a gate-severity finding, **When** the developer runs the SAST target, **Then** the target exits nonzero and the finding appears in output.
3. **Given** Semgrep is not installed, **When** the developer runs the SAST target, **Then** the target exits nonzero with an actionable "not installed" error — not a silent skip, not a success.
4. **Given** Semgrep encounters an internal error, **When** the developer runs the SAST target, **Then** the error output is visible (not discarded) and the step does not report success.

---

### User Story 2 - Fresh environment setup includes the scanner (Priority: P2)

A developer provisions a fresh development environment from the project's pinned development dependencies. Semgrep is installed at a pinned version as part of that standard setup, with no extra manual steps. Two developers provisioning on different days get the same Semgrep version and the same scan results.

**Why this priority**: Unconditional invocation (US1) is only safe if provisioning guarantees the tool exists; otherwise the loud error fires on every fresh clone and the gate gets reverted as a nuisance.

**Independent Test**: In a fresh virtual environment, install the development dependencies, confirm Semgrep is present at the pinned version, and confirm the SAST target runs it successfully.

**Acceptance Scenarios**:

1. **Given** a fresh environment, **When** development dependencies are installed, **Then** Semgrep is present at the pinned version.
2. **Given** two environments provisioned from the same dependency pin, **When** each runs the SAST target on the same tree, **Then** both run the same scanner version in the same rules mode. (Identical outcomes are NOT guaranteed: auto-config rule content floats server-side, an accepted trade-off — see Context and Edge Cases.)

---

### User Story 3 - Pre-existing findings are dispositioned before the gate flips (Priority: P1)

The gate lands only against a measured, clean baseline. Every finding Semgrep reports on the current codebase at gate severity is either fixed or suppressed with a documented justification following the repo's existing SAST suppression policy (understand the pattern, fix or justify, never rename-to-evade). The first post-merge run of the SAST target on an unmodified tree passes.

**Why this priority**: Shares P1 with US1 because the gate cannot merge without it — a gate that fails on day one for every developer is a gate that gets bypassed or reverted, which is worse than the current silence.

**Independent Test**: Run the SAST target on the unmodified post-change tree; exit code is zero, and any suppressions added carry written justification.

**Acceptance Scenarios**:

1. **Given** the post-change tree with no developer modifications, **When** the SAST target runs, **Then** it exits zero.
2. **Given** any suppression added during baseline cleanup, **When** a reviewer inspects it, **Then** it carries a documented justification in an adjacent comment, discoverable by a code-surface search for the scanner's suppression marker (per SC-006 — the repo's pragma audit does not yet cover this marker; extending it is owned by the bandit-to-semgrep migration card).

---

### Edge Cases

- Scanner fetches rules from the vendor registry on EVERY run (not just the first): every SAST run takes a network dependency and ~15s. Acceptable for a pre-push local gate; a network-failure run must fail visibly, not pass silently (no-swallow requirement covers it). Offline developers cannot run the full validation suite — accepted.
- Registry-side rule drift (the real 3am case): the vendor can ship a new or retuned gate-severity rule overnight, turning an unmodified tree red with zero repo changes. This is expected behavior of auto-config mode, not a repo defect. Remedy: fix or suppress-with-justification, same as any finding; never re-neuter the gate. Success criteria for a clean tree are therefore pinned to merge time.
- Version drift between two developers: prevented by pinning; floating installs are out of policy.
- A future finding blocks urgent work: the documented suppression path exists per repo SAST policy; bypassing the gate wholesale (skip flags, swallows) must not be reintroduced.
- Runtime cost: Semgrep adds tens of seconds to the SAST target; acceptable for a pre-push local gate, and developers who want faster loops run narrower targets.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The scanner MUST be pinned at one exact version across both provisioning surfaces that exist for it today: the pinned development requirements (add) and the packaging dev extra (currently a floating minimum — tightened to the same exact pin). The CI requirements file is deliberately NOT changed: no CI job runs the SAST target today, and adding a ~100MB install to every CI run for an unused tool is waste; CI provisioning lands with the validator-gating family when CI SAST wiring lands (recorded in Follow-ups and on the board card evidence).
- **FR-002**: The SAST target MUST invoke the scanner unconditionally — no presence check that converts absence into a skip.
- **FR-003**: If the scanner is absent or fails to start, the SAST target MUST exit nonzero with an actionable error message.
- **FR-004**: Findings at the gate severity MUST cause the SAST target to exit nonzero; no construct may convert that failure into success (no `|| true`, `|| echo`, or equivalent).
- **FR-005**: The scanner's error output MUST reach the developer (no discarding of stderr).
- **FR-006**: The gate MUST land against a clean baseline: all pre-existing gate-severity findings on the current codebase are fixed or suppressed-with-justification in the same feature, so an unmodified tree passes.
- **FR-007**: The bandit step of the SAST target MUST remain byte-identical (its swallow is owned by the separate bandit-to-semgrep migration card, explicitly out of scope here).
- **FR-008**: The scanner's rules mode MUST remain what the target uses today (auto-config); rule curation beyond what hard-fail requires is out of scope.
- **FR-009**: The semgrep portion of the shared board card ("Orphaned validators: semgrep not installed, LocalStack integration and mutmut never run") MUST be closed with dated evidence as part of feature completion. The card as a whole moves lanes ONLY if its LocalStack/mutmut decisions are also closed; otherwise the card is split or annotated, never falsely closed.

### Key Entities

- **SAST gate**: The Semgrep step of the `sast` target — the unit being converted from decorative to blocking.
- **Baseline disposition**: The set of fixes and justified suppressions that make the unmodified tree pass at gate severity before the gate flips on.
- **Gate severity**: The finding-severity threshold at which the target fails — ERROR and WARNING, today's invocation unchanged (confirmed against the measured baseline; see Clarifications).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a provisioned environment with an unmodified tree, the SAST target exits zero and its output shows the scanner actually ran (rule/file counts visible).
- **SC-002**: With a planted gate-severity finding, the SAST target exits nonzero and names the finding; removing the plant restores exit zero.
- **SC-003**: With the scanner uninstalled, the SAST target exits nonzero with an actionable error; the missing-scanner detection itself adds under 5 seconds (the preceding frozen bandit step's own ~4-5s runtime is outside this budget — it runs first and is byte-identical per FR-007). Fail-fast, not a hang or a skip.
- **SC-004**: A search of the SAST target's scanner step shows zero output-swallowing constructs and zero presence-check skips.
- **SC-005**: Fresh provisioning from pinned development dependencies yields the scanner at the pinned version with zero manual steps beyond the documented standard setup.
- **SC-006**: Every suppression added during baseline cleanup carries written justification in an adjacent comment, discoverable by a code-surface search for the scanner's suppression marker. (The repo's existing pragma audit covers only the linter/bandit markers; extending it to scanner suppressions is explicitly owned by the bandit-to-semgrep migration card.)

## Assumptions

- No CI workflow runs the SAST target today (verified in the sibling tfsec feature's reviews); this feature is a local-gate fix, and CI wiring of SAST remains owned by the validator-gating feature (1400) family.
- The repo's existing SAST policy sections (suppression discipline, pragma audit) apply unchanged; this feature adds no new policy.
- The pinned version is `semgrep==1.172.0` — the release the baseline was measured with; the pin lives with the other security tooling pins in the development dependencies.
- Network access is available on developer machines for rule download in auto-config mode (already true for dependency installation generally).
- Auto-config mode sends pseudonymous scan metrics to the vendor on every run, with no printed notice. This is accepted knowingly for the local gate. (Planning verified a metrics-off flag is hard-incompatible with auto-config — the scanner refuses to start — so the acceptance is final; see Clarifications.)

## Follow-ups (out of scope, recorded so they have an owner)

- **Bandit swallow** (`|| true` on the bandit step): owned by the bandit-to-semgrep migration card, post-push.
- **CI wiring of the SAST target**: owned by the validator-gating (1400) family.
- **Rule curation** (project-specific semgrep rulesets, ignore files): baseline measurement (3 findings) forced no curation decision; deferred.
- **CI provisioning of the scanner** (CI requirements pin): lands with the validator-gating (1400) family's CI SAST wiring — the semgrep clause of the board card's per-tool next-action ("pin+install+CI semgrep or drop it from make sast") is split accordingly, venv now, CI deferred.
- **Scanner-suppression audit** (nosemgrep coverage in the pragma audit): owned by the bandit-to-semgrep migration card.

## Adversarial Review #1

Independent hostile review (agent aed2659802078c0c6, 2026-07-29) ran the scanner empirically (semgrep 1.172.0 in a throwaway environment) against the live tree and returned 3 HIGH, 3 MEDIUM, 2 LOW, 1 INFO findings. All resolved by spec edits below; the empirical baseline is now embedded in Context.

| ID | Severity | Finding | Resolution |
|----|----------|---------|------------|
| F1 | HIGH | US2 acceptance scenario 2 promised identical outcomes across environments from the same pin — false under auto-config, where rule content floats server-side regardless of engine pin. | Scenario reworded: same version + same rules mode guaranteed, identical outcomes explicitly NOT; trade-off cross-referenced to Context and Edge Cases. |
| F2 | HIGH | Baseline is perishable: registry-side rule drift can turn an unmodified tree red overnight with zero repo changes, and the spec had no story for it. | Edge case added naming registry drift as expected auto-config behavior (remedy: fix or suppress, never re-neuter); clean-tree success criteria pinned to merge time. |
| F3 | HIGH | SC-006 was vacuous: it required suppressions to pass the repo's pragma audit, but audit-pragma covers only `# noqa`/`# nosec` — it has zero nosemgrep coverage, so any suppression would trivially "pass". | SC-006 weakened to grep-reviewable adjacent justification; extending the pragma audit to nosemgrep explicitly handed to the bandit-to-semgrep migration card. |
| F4 | MEDIUM | FR-009 would falsely close a shared board card: "Orphaned validators" also tracks LocalStack integration and mutmut, which this feature does not touch. | FR-009 rewritten to close only the semgrep portion with dated evidence; card moves lanes only if its other decisions are also closed — split or annotate, never falsely close. |
| F5 | MEDIUM | Two-path version drift: pyproject.toml:55 declares `semgrep>=1.50.0` (floating) in the dev extra while FR-001 only added a pin to requirements-dev.txt — the two surfaces could diverge. | FR-001 rewritten to pin one exact version across BOTH surfaces (requirements-dev.txt add, pyproject dev extra tightened to the same pin). |
| F6 | MEDIUM | requirements-ci.txt was silently undecided — neither pinned nor excluded with rationale. | FR-001 now records the deliberate exclusion: no CI job runs the SAST target today; ~100MB per CI run for an unused tool is waste; CI provisioning lands with the validator-gating (1400) family (Follow-ups + board evidence). |
| F7 | LOW | "Network access on first run" understated the dependency: auto-config fetches ~1032 registry rules on EVERY run (~15s, measured). | Edge case corrected to every-run fetch with measured cost; offline developers accepted as unable to run full validation. |
| F8 | LOW | Auto-config sends pseudonymous scan metrics to the vendor on every run with no printed notice; spec was silent. | Assumption added accepting this knowingly; planning verifies whether a metrics-off flag is compatible with registry configs and applies it if zero-cost. |
| F9 | INFO | Baseline measured: exactly 3 gate-severity findings, all ERROR — missing-user ×2 (src/lambdas/analysis/Dockerfile:57, src/lambdas/dashboard/Dockerfile:60), tarfile extractall traversal ×1 (src/lambdas/analysis/sentiment.py:117-118, line already carries `# nosec B108 B202`). Zero nosemgrep comments repo-wide; no .semgrep.yml/.semgrepignore; untracked planted files ARE scanned. | Recorded in Context as the closed three-item worklist; dispositions decided during planning (sse_streaming Dockerfile:77 `USER lambda` precedent exists BUT image-Lambda crash-loop history at 118ab27 means suppression-with-justification may beat a USER change; extractall fixable with `filter="data"` on Python 3.13). |

Verified-OK (held under attack): sast target's skip+swallow+stderr-discard claims accurate against Makefile:73-84; no CI workflow runs make sast (re-confirmed); `--error` is the canonical gating flag; plant test viable (untracked files scanned).

**Gate: 0 CRITICAL, 0 HIGH remaining.**
