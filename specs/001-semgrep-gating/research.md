# Research: Make the SAST Semgrep Step a Real Gate

**Feature**: 001-semgrep-gating | **Date**: 2026-07-29

All unknowns from the Technical Context resolved. Each entry: Decision / Rationale / Alternatives considered.

## R1: Which exact version to pin, and where?

**Decision**: `semgrep==1.172.0` in both provisioning surfaces: added to `requirements-dev.txt` (adjacent to the `bandit==1.9.4` pin at line 38) and tightened in `pyproject.toml` line 55 (`semgrep>=1.50.0` → `semgrep==1.172.0`). `requirements-ci.txt` deliberately untouched (FR-001).

**Rationale**: 1.172.0 is the exact version AR#1 measured the 3-finding baseline against (2026-07-29). Pinning the measured version means the gate lands against a baseline verified with the same engine — no re-measurement risk between planning and implementation. It is a current stable release.

**Alternatives considered**: Pinning latest-at-implementation-time — rejected: invalidates the measured baseline for zero benefit; the ruff-skew memory shows what version drift between surfaces costs this repo. Range pin (`~=1.172`) — rejected: FR-001 and US2 require one exact version.

## R2: Is `--metrics=off` compatible with `--config auto`?

**Decision**: NOT compatible — the flag is not applied. The spec's telemetry assumption (pseudonymous metrics accepted knowingly) stands as final.

**Rationale**: Verified empirically this session (semgrep 1.172.0): `semgrep scan --config auto --metrics=off ...` exits 2 immediately with `Cannot create auto config when metrics are off. Please allow metrics or run with a specific config.` The spec's condition was "if compatible at zero cost, apply it" — it is incompatible at any cost, so the acceptance in Assumptions is the outcome.

**Alternatives considered**: Switching to a pinned ruleset config (e.g., `--config p/default`) to enable metrics-off — rejected: FR-008 freezes auto-config mode per the card's scope; rule curation is an explicit non-goal.

## R3: What does the hardened `sast` recipe look like?

**Decision**: Replace the skip/swallow block of the `sast` target — Makefile lines **78-83**, keeping the line-77 `Running Semgrep` heading echo and the line-84 trailing success echo — with:

```make
	@command -v semgrep >/dev/null 2>&1 || { \
		echo "$(RED)✗ Semgrep not installed. Install: pip install -r requirements-dev.txt$(NC)"; \
		exit 1; }
	semgrep scan --config auto --error --severity ERROR --severity WARNING src/
```

Scan flags are byte-identical to today's invocation; only the neutering constructs are removed (presence-check skip, `2>/dev/null` stderr discard, `|| echo` findings swallow).

**Rationale**:
- FR-002 forbids a presence check *that converts absence into a skip*. A presence check that converts absence into a loud nonzero failure with an install command satisfies both FR-002's intent and FR-003's "actionable error" requirement, and meets SC-003's <5s fail-fast (the check is instant; a bare `semgrep: command not found` from the shell would exit fast too but is less actionable).
- Findings failure propagates naturally: `--error` makes semgrep exit 1 on findings; with no `||` construct, make stops and the target exits nonzero, so the trailing `✓ SAST scan complete` echo never prints on failure (SC-001's "output shows the scanner ran" comes from semgrep's own rule/file count summary, no longer discarded).
- The bandit lines (75, `bandit ... || true`) remain byte-identical (FR-007).

**Alternatives considered**: Bare invocation with no check (option a) — rejected: exit 127 with `make: semgrep: No such file or directory` is fast but not actionable per SC-003's wording. Wrapper script — rejected: more surface than a two-line recipe change warrants.

## R4: Gate severity confirmation

**Decision**: Keep today's threshold exactly: `--error --severity ERROR --severity WARNING`.

**Rationale**: The spec's Key Entities defers the exact threshold to planning, confirmed against the measured baseline. AR#1 measured with precisely these flags: 3 findings, all ERROR, zero WARNING. Keeping WARNING in scope costs nothing today (zero WARNING findings) and preserves the target's advertised strictness; narrowing to ERROR-only would silently weaken the gate relative to what the Makefile has always claimed to check.

**Alternatives considered**: ERROR-only — rejected as a silent weakening with no baseline pressure justifying it.

## R5: Disposition of the 3 baseline findings

### R5a: `dockerfile.security.missing-user` ×2 (analysis/Dockerfile:57, dashboard/Dockerfile:60)

**Decision**: Suppress with `# nosemgrep: dockerfile.security.missing-user.missing-user` **on its own line immediately above** each flagged `CMD` line, with the justification comment adjacent. The `CMD` lines themselves stay byte-identical. Do NOT add a `USER` directive.

**Placement is load-bearing (AR#2 F1)**: a trailing comment ON a Dockerfile `CMD` line is not a comment — Docker folds it into the instruction, silently flipping exec form to shell form and garbling the handler string (verified empirically via `docker inspect`; it is exactly the 118ab27 crash-loop shape). Line-above placement verifiably suppresses the finding (0 findings, exit 0) with Dockerfile semantics untouched. Verification asserts the CMD lines are unchanged vs main.

**Rationale**: Both images use the AWS managed base image (`public.ecr.aws/lambda/python:3.13`) and carry demonstrated crash-loop history (118ab27) for runtime-environment changes — the verifiable core of the justification. The Lambda platform's sandbox isolation stands as defense-in-depth against the rule's threat (root container processes); the sse_streaming image sets `USER lambda` because it is a custom-bootstrap image with its own entrypoint, a different execution model. The one image with `USER lambda` (sse_streaming/Dockerfile:77) is a custom-bootstrap streaming image that does not use the managed runtime entrypoint — a different execution model, not a precedent for these two. Against that marginal benefit stands documented crash-loop history on exactly these image Lambdas (commit 118ab27, two rounds): runtime-environment changes to working images carry real, demonstrated risk here. Suppression-with-justification is the repo's SAST policy for exactly this shape: understood pattern, platform-level mitigation, documented.

**Alternatives considered**: Adding `USER` per the sse_streaming pattern — rejected: demonstrated crash-loop risk on these Lambdas vs. a finding whose threat the platform sandbox already blunts; would also require a deploy-and-verify cycle far outside a toolchain card's scope. Same-line suppression — rejected outright per the placement finding above.

### R5b: `tarfile extractall` traversal (analysis/sentiment.py:117-118)

**Decision**: Fix properly: `tar.extractall(path="/tmp", filter="data")`. Keep the existing `# nosec B108 B202` comment unchanged. Accompany with a new unit test (constitution's accompaniment rule) scoped to what is actually uncovered: traversal/absolute-path member REJECTION under `filter="data"` (verified: raises `OutsideDestinationError`). The happy path is already covered — `tests/unit/test_sentiment.py`'s `TestS3ModelDownload` class overrides the module-level mock and runs the real extraction against a locally built tarball (AR#2 F2 corrected the earlier zero-coverage claim), so the existing suite regression-covers the new argument for free.

**Rationale**: Python 3.13's `filter="data"` rejects path-traversal members, absolute paths, symlinks/hardlinks escaping the destination, and strips dangerous metadata — it eliminates the vulnerability class the rule detects rather than suppressing the warning. The project runs 3.13 everywhere (pyproject `requires-python >= 3.13`, Lambda base image 3.13), so the argument is safe. The nosec comment stays untouched: bandit pragma churn belongs to the bandit-to-semgrep migration card.

**Suppression rider (AR#3 F2 — verified, this is the mainline, not a contingency)**: the trailofbits rule flags the line even WITH `filter="data"` — its pattern matches `tarfile.open(...)...extractall()` regardless of the filter argument. So the real fix is accompanied by `# nosemgrep: trailofbits.python.tarfile-extractall-traversal.tarfile-extractall-traversal` (full doubled-segment registry id — targeted nosemgrep requires an exact match; the short form verifiably does not suppress) with justification on its own line immediately ABOVE the `with tarfile.open(...)` line (117) — the finding's match starts at the `with` line, and a trailing marker on the extractall line verifiably does NOT suppress. Expected code-surface nosemgrep count: 3 (two Dockerfiles + sentiment.py).

**Alternatives considered**: Suppress-only — rejected: a one-argument real fix beats a suppression when both cost the same line. Member-by-member validation loop — rejected: `filter="data"` is the stdlib's canonical answer since 3.12.

## R6: Board card portion-close mechanics

**Decision**: String surgery on the minified CARDS JSON in `CLEANUP-BOARD.html` (same technique as the tfsec feature): the "Orphaned validators: semgrep not installed, LocalStack integration and mutmut never run" card stays in lane `track`; its evidence gains a dated clause closing the semgrep portion (pinned version, gate flipped, baseline dispositioned, date). Its live `next_action` reads (AR#2-verified actual text): "Per-tool wire-or-delete decision: pin+install+CI semgrep or drop it from make sast; stand up LocalStack CI or delete the target; add mutmut config+CI or remove the target." — the rewrite closes the semgrep clause of that per-tool decision as "semgrep: pinned+installed in venv, gate flipped (done 2026-07-29); CI provisioning deferred to 1400 family", leaving the LocalStack and mutmut clauses untouched.

**Rationale**: FR-009 as amended by AR#1 F4 — the card is shared; closing it wholesale would falsely close the LocalStack/mutmut decisions. Verified via `json.raw_decode` after edit, as Feature 1 did.

**Alternatives considered**: Splitting into two cards — viable but heavier; annotation preserves card history in one place and the split option remains open to the LocalStack/mutmut decision-maker.

## R7: Plant-test pattern for SC-002

**Decision**: Verification plants an untracked file under `src/` containing a known ERROR-severity pattern (e.g., `subprocess` call with `shell=True` on tainted input, a pattern in the default registry at ERROR), runs `make sast`, asserts nonzero exit and the rule id in output; deletes the plant, asserts exit zero.

**Rationale**: AR#1 verified untracked files ARE scanned (semgrep scans the filesystem, not git index), so the plant never risks entering history. Exact plant content is chosen at implementation against the live registry (auto-config rules float; the plant must trip a rule present that day — the verification runbook says "any gate-severity rule", not one hardcoded id).
