# Implementation Plan: Make the SAST Semgrep Step a Real Gate

**Branch**: `001-semgrep-gating` | **Date**: 2026-07-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-semgrep-gating/spec.md`

## Summary

Convert the Makefile `sast` target's Semgrep step from triple-neutered (presence-check skip, findings swallow, stderr discard) to a hard gate, pin `semgrep==1.172.0` across both provisioning surfaces (requirements-dev.txt add, pyproject.toml dev-extra tighten), and land against the measured 3-finding baseline: two Dockerfile missing-user findings suppressed via line-ABOVE nosemgrep markers (same-line comments corrupt CMD — AR#2 F1) justified by 118ab27 crash-loop history with the platform sandbox as defense-in-depth, one tarfile extractall fixed properly with `filter="data"` plus a new unit test scoped to traversal-member rejection (happy path already covered by TestS3ModelDownload) and a nosemgrep rider above the `with` line (the rule ignores the filter argument — AR#3 F2), bringing expected code-surface suppressions to 3. `--metrics=off` verified incompatible with auto-config (hard error, exit 2) — not applied; the spec's telemetry acceptance stands. Bandit step byte-identical (FR-007). Board card portion-closed with dated evidence, never falsely closed (FR-009).

## Technical Context

**Language/Version**: GNU Make (recipe edit), pip requirements + TOML (two pin edits), Python 3.13 (one-argument fix in `src/lambdas/analysis/sentiment.py` + one new unit test), Dockerfile comments (two suppressions), HTML (board card string surgery).
**Primary Dependencies**: `semgrep==1.172.0` added to requirements-dev.txt; pyproject dev extra tightened from `>=1.50.0` to the same pin. requirements-ci.txt untouched (FR-001). No runtime dependencies change.
**Storage**: N/A
**Testing**: Behavioral verification per quickstart runbook (clean-tree pass, plant test, missing-binary fail-fast, swallow-construct grep, fresh-provision check); one new unit test for traversal-member rejection under `filter="data"` (the happy-path extraction is already covered: `TestS3ModelDownload` in tests/unit/test_sentiment.py overrides the module mock and runs real extraction, so it regression-covers the new argument; member-rejection behavior is the uncovered part); full unit suite must stay green.
**Target Platform**: Developer workstations (Linux/WSL2). No CI workflow runs `make sast` today (verified AR#1 + tfsec feature reviews); CI wiring stays with the 1400 family.
**Project Type**: Single project, tooling change + one-line code fix.
**Performance Goals**: `make sast` semgrep step ~15s measured (registry fetch dominates); constitution §10 requires `make sast` < 60s — satisfied with margin.
**Constraints**: FR-007 bandit lines byte-identical; FR-008 auto-config frozen; GPG-signed commits; no new AWS resources (trivially satisfied); RUFF CHURN LANDMINE — after any `make validate`, discard reflow with `git checkout -- src tests` until the ruff feature lands.
**Scale/Scope**: ~6 Makefile lines replaced by ~4, 2 pin edits, 2 Dockerfile comment lines, 1 Python argument + 1 test file, 1 board card annotation.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Justification |
|------|--------|---------------|
| Unit tests accompany all implementation code | PASS | The one code change (`filter="data"`) gains a new unit test covering traversal-member rejection; existing `TestS3ModelDownload` tests exercise the real extraction happy path and regression-cover the new argument. Makefile/pins/comments have no unit-testable surface; behavioral verification substitutes (quickstart). |
| External dependencies mocked in tests | PASS | New unit test uses a locally-built tarball in `tmp_path`; S3 stays mocked as in existing tests. |
| Pre-push requirements (ruff lint/format, GPG-signed, feature branch) | PASS | Branch `001-semgrep-gating`; GPG-signed; the sentiment.py edit passes ruff (argument addition, no reflow). |
| Local SAST before push | PASS — and strengthened | This feature IS the constitution §10(b) requirement ("Make validate (Semgrep): comprehensive SAST before push") becoming true. Today §10's acceptance criterion "`make sast` runs Bandit + Semgrep" is false on every standard-provisioned machine (silent skip). The feature closes a constitution compliance gap; it does not touch the constitution text. |
| Tech debt tracking | PASS | Two suppressions carry in-place documented justification per repo SAST policy (SC-006); the deliberate CI-provisioning deferral is recorded in spec Follow-ups + board card evidence. No new registry entry needed: the debt being tracked (orphaned validator) is being *retired*, and remaining portions (LocalStack/mutmut, CI wiring, bandit swallow) already have named owners on the board. |
| No new AWS resources | PASS | Nothing infrastructural; Dockerfile edits are comments only. |

**Post-design re-check (after Phase 1)**: unchanged — PASS on all gates. No Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-semgrep-gating/
├── spec.md              # Stage 1 + AR#1 appendix
├── plan.md              # This file
├── research.md          # Phase 0 output (R1-R7, all unknowns resolved)
├── data-model.md        # Phase 1 output (minimal — no data entities)
├── quickstart.md        # Phase 1 output (verification runbook)
├── checklists/
│   └── requirements.md  # Spec quality checklist (passed)
└── tasks.md             # Phase 2 output (/speckit.tasks — not yet created)
```

### Source Code (repository root)

```text
Makefile                          # sast target lines 78-83 replaced (heading echo 77 + trailing echo 84 kept; bandit lines 74-75 byte-identical)
requirements-dev.txt              # add semgrep==1.172.0 near bandit pin (line 38)
pyproject.toml                    # line 55: semgrep>=1.50.0 → semgrep==1.172.0
src/lambdas/analysis/Dockerfile   # nosemgrep + justification on own lines ABOVE CMD (line 57); CMD byte-identical
src/lambdas/dashboard/Dockerfile  # nosemgrep + justification on own lines ABOVE CMD (line 60); CMD byte-identical
src/lambdas/analysis/sentiment.py # line 118: extractall(path="/tmp", filter="data")
tests/unit/test_sentiment.py      # new test(s): extraction with filter="data"
CLEANUP-BOARD.html                # "Orphaned validators" card: dated semgrep-portion close + next_action split
```

**Structure Decision**: No source tree changes. Eight existing files edited in place plus new test code; no files created outside `specs/001-semgrep-gating/` except test additions.

## Verification Design

Maps success criteria to concrete checks (full commands in quickstart.md):

1. **SC-001 (clean pass, visibly ran)**: `make sast; echo $?` on unmodified post-change tree → exit 0; output contains semgrep's rule/file count summary (no longer discarded).
2. **SC-002 (plant test)**: untracked ERROR-pattern file under `src/` → `make sast` nonzero, rule id visible; delete plant → exit 0. Plant chosen against live registry at implementation (R7).
3. **SC-003 (fail-fast when missing)**: shadow semgrep off PATH (same PATH-filter technique as tfsec feature) → `time make sast` nonzero with the install-command message; budget is <5s for the detection itself, ~10s total on the runbook machine (the frozen bandit step runs first and consumes ~4-5s — AR#2 F4).
4. **SC-004 (no swallows)**: grep the sast recipe's semgrep lines for `|| true`, `|| echo`, `2>/dev/null`, `if command -v ... then ... else` skip-shape → zero hits (bandit lines exempt per FR-007; the retained `command -v` guard fails loudly, not skips — FR-002/FR-003 compliant per R3).
5. **SC-005 (fresh provision)**: fresh venv, `pip install -r requirements-dev.txt`, `semgrep --version` → 1.172.0; `pip install -e .[dev]` resolves to the same pin (no conflict between surfaces).
6. **SC-006 (suppression justification)**: `grep -rn nosemgrep` constrained to code surfaces (`--include=Dockerfile --include='*.py' --include=Makefile`) → exactly 3 hits (two Dockerfiles + sentiment.py per AR#3 F2), each with adjacent justification comment. (An unconstrained repo-wide grep also hits this feature's own spec artifacts and archived docs — 13 hits pre-existing — so the code-surface constraint is what makes the check meaningful; AR#2 F3.) Additionally `git diff main -- src/lambdas/analysis/Dockerfile src/lambdas/dashboard/Dockerfile` shows only added comment lines; the CMD lines are byte-identical (AR#2 F1).
7. **FR-007 (bandit frozen)**: `git diff main -- Makefile` touches only the semgrep block lines.
8. **FR-009 (board)**: parse CARDS JSON via `json.raw_decode`; "Orphaned validators" card evidence contains dated semgrep-close clause; next_action reflects venv-done/CI-deferred split; lane unchanged.
9. **Unit suite**: `pytest tests/unit/ -v` green, including the new extraction test.

## Complexity Tracking

No constitution violations; table intentionally empty.

## Adversarial Review #2

Independent cross-artifact review (agent a372f70d1e64bf325, 2026-07-29) after the Clarifications session, with empirical verification (throwaway semgrep 1.172.0, repo venv Python 3.13.0, local Docker). Verdict: 0 CRITICAL, 1 HIGH, 4 MEDIUM, 2 LOW — all resolved by artifact edits below.

| ID | Severity | Finding | Resolution |
|----|----------|---------|------------|
| F1 | HIGH | Same-line `# nosemgrep` on a Dockerfile CMD line is not a comment — Docker folds it into the instruction (verified via `docker inspect`: flips exec form to shell form, garbles the handler string — the 118ab27 crash-loop shape). Semgrep suppresses from BOTH placements, so every planned check would pass on the broken variant; only a deploy would expose it. | R5a/plan/data-model/Clarifications now mandate the marker on its own line immediately ABOVE the CMD (verified: suppresses, semantics untouched); new verification asserts CMD lines byte-identical vs main. |
| F2 | MEDIUM | "Zero extraction coverage" was false: `TestS3ModelDownload` (tests/unit/test_sentiment.py:440-620) overrides the module mock and runs the real extraction against a locally built tarball. | Artifacts corrected: happy path covered (and regression-covers the new argument for free); new test scoped to what IS uncovered — traversal-member rejection under `filter="data"`. |
| F3 | MEDIUM | "Exactly 2 nosemgrep hits" repo-wide grep already returns 13 today (this feature's own spec artifacts + archived 070 docs); post-merge ~15. | Sweep constrained to code surfaces (`--include=Dockerfile --include='*.py' --include=Makefile`); expectation reworded. |
| F4 | MEDIUM | SC-003's <5s was measured over the whole `make sast`, but the frozen bandit step alone consumes ~4.4s (measured) and runs first — the check was borderline-flaky by construction. | SC-003 respecified: <5s budget applies to the missing-scanner detection itself (guard measured at 0.036s); runbook bound ~10s total with bandit noted as dominating. |
| F5 | MEDIUM | Replace-range contradiction: R3 said replace lines 77-83 (which deletes the `Running Semgrep` heading), while quickstart step 5's sed anchors on that heading — the no-swallow sweep would pass vacuously on empty output. | R3 pinned to replacing lines 78-83, keeping the line-77 heading echo and line-84 trailing echo; plan structure note aligned. |
| F6 | LOW | Board card `next_action` misquoted ("install in venv + CI" appears nowhere); string surgery targeting it would miss. | R6 and spec Follow-ups now quote the actual per-tool text and describe the semgrep-clause rewrite against it. |
| F7 | LOW | The suppression justification's categorical claim (Lambda runs code non-root "regardless of USER") was unverified and mildly undercut by the repo's own sse_streaming USER directive. | Justification re-led with the verifiable rationale: 118ab27 crash-loop history vetoes runtime changes; platform sandbox cited as defense-in-depth, not as a categorical guarantee. |

Verified-OK (held under attack): Makefile line map (bandit 74-75, semgrep block 77-84) exact; pyproject.toml:55 and requirements-dev.txt:38 exact; no CI workflow touches make sast/validate/semgrep (only a comment at pr-checks.yml:13); Dockerfile/sentiment.py claims exact; metrics-off incompatibility reproduced verbatim (exit 2); `filter="data"` raises OutsideDestinationError on traversal members (repo venv 3.13.0); quickstart plant pattern trips `python.lang.security.audit.subprocess-shell-true.subprocess-shell-true` as Blocking; rule id `dockerfile.security.missing-user.missing-user` confirmed with line-above suppression working; R3 recipe mechanics verified in isolation (guard exits nonzero in 0.036s, make stops before trailing echo on scanner exit 1, backslash-continuation precedent exists, no .ONESHELL/.SHELLFLAGS overrides); board parse script runs as-is against live CLEANUP-BOARD.html (card in lane `track`); constitution <60s ceiling at constitution.md:636; FR-002 vs loud-fail guard internally consistent.

**Gate: 0 CRITICAL, 0 HIGH remaining.**
