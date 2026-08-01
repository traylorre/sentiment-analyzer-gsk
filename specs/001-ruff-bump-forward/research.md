# Research: Ruff Bump-Forward

**Date**: 2026-07-29 | **Feature**: [spec.md](spec.md)

Most items below were resolved *empirically* during AR#1 (agent aef0c1895ca54127c installed ruff 0.8.4 and 0.15.14, ran both against the live tree, pulled tags via ls-remote, fetched hook definitions at the exact tag). This file consolidates those results plus plan-phase verification into decisions.

## R1 — Target version and availability

**Decision**: ruff 0.15.14, everywhere.
**Rationale**: Two surfaces (requirements-dev.txt:36, requirements-ci.txt:57) already pin it; the sibling toolchain features standardized on it; PyPI package verified installable.
**Alternatives considered**: chase latest ruff (rejected: moving target mid-feature, and the battleplan's purpose is convergence, not currency); stay on 0.8.4 and downgrade the requirements pins (rejected: walks the repo backward 15 months of formatter/linter fixes and still requires a reformat since the venv drifted).

## R2 — Pre-commit rev and hook ids

**Decision**: `rev: v0.15.14`, hook id `ruff-check` (adopting the rename), `ruff-format` unchanged, `args: [--fix]` preserved.
**Rationale**: Tag `v0.15.14` verified to exist (ls-remote, sha `0c7b6c98`). Its `.pre-commit-hooks.yaml` defines `ruff-check`, `ruff-format`, and `ruff` as an explicit "Legacy alias" — so the rename is not forced at this rev, but the alias can vanish in any future rev; adopting `ruff-check` now removes a future breakage for one line of diff.
**Alternatives considered**: keep legacy id `ruff` (rejected: known-deprecated name, zero cost to fix now); pin by sha instead of tag (rejected: repo convention is version tags across all hooks).

## R3 — required-version syntax and enforcement semantics

**Decision**: `required-version = "==0.15.14"` under `[tool.ruff]` in pyproject.toml.
**Rationale**: Both `"==0.15.14"` and `"0.15.14"` verified accepted by 0.15.14; the explicit `==` form self-documents that it is an exact-match specifier (the setting also accepts ranges). Enforcement verified: stale ruff 0.14.11 refuses to run BOTH `check` and `format` (exit 2, sub-second, actionable message). Critically, pre-commit's isolated-env ruff also reads the project pyproject and enforces it — which is the desired lockstep (rev must equal required-version forever) and the reason FR-010 rewrites the autoupdate runbook.
**Alternatives considered**: version-range pin like `>=0.15,<0.16` (rejected: reintroduces intra-range drift, the exact disease); no enforcement, docs only (rejected: docs are how the five-way disagreement happened).

## R4 — New-finding set at 0.15.14 and disposition

**Decision**: 7× `# noqa: UP042` riders, one per flagged enum, each with a one-line justification; no code fix.
**Rationale**: Complete measured set (2026-07-29): UP042 ("class inherits from both str and Enum — use StrEnum") on:

| Enum | Location |
|---|---|
| `Resolution` | src/lib/timeseries/models.py:17 |
| `SentimentSource` | src/lambdas/analysis/sentiment.py:353 |
| `SentimentLabel` | src/lambdas/analysis/sentiment.py:361 |
| `AuthErrorCode` | src/lambdas/shared/errors/auth_errors.py:20 |
| `AuthType` | src/lambdas/shared/middleware/auth_middleware.py:27 |
| `TimeRange` | src/lambdas/shared/models/ohlc.py:16 |
| `OHLCResolution` | src/lambdas/shared/models/ohlc.py:36 |

Ruff marks the StrEnum autofix **unsafe**: `str(StrEnum.MEMBER)` returns the value where `str(str-Enum.MEMBER)` returns `"ClassName.MEMBER"` — a live behavior difference for anything that formats/serializes these members, and all seven serialize to DynamoDB/JSON. Behavior-neutrality (spec assumption) therefore forbids the fix.
**Alternatives considered**: StrEnum migration (rejected here; recorded as the proposed fix on the CLEANUP-BOARD.html kanban card, a future feature with its own serialization test sweep); per-file-ignores for UP042 (rejected: broader than needed, hides future violations in those files); global UP042 ignore (prohibited by FR-006).

## R5 — audit-pragma repair mechanism

**Decision**: Makefile audit-pragma recipe: `ruff check --select RUF100 src/ tests/` → `ruff check --extend-select RUF100 src/ tests/`.
**Rationale**: CLI `--select` REPLACES the configured select set, so noqas referencing rules outside RUF100 (all the S-rule suppressions) evaluate as "unused" — 14 false positives today under every ruff version including the current CI 0.8.4. `--extend-select` composes with the config instead. Verified during planning that `RUF100` is ALREADY in the pyproject select list (pyproject.toml `[tool.ruff.lint]` select), so the main lint gate correctly reports zero unused noqas; the extend-select form is equivalent on today's config and stays correct even if RUF100 is ever dropped from the config list. Bandit half of the target (`--ignore-nosec` audit) untouched.
**Alternatives considered**: delete the RUF100 half as redundant with `make lint` (rejected: the target's documented purpose is a focused pragma audit; keeping it costs one flag); `--select RUF100,S,E,W,...` mirroring config (rejected: second copy of the select list to drift).

## R6 — Dependabot drift-channel closure

**Decision**: add to `.github/dependabot.yml` pip ecosystem block: an `ignore` entry for `ruff` (all update types), with comment "ruff upgrades are deliberate multi-surface operations (see specs/001-ruff-bump-forward): pins exist in requirements-dev, requirements-ci, pyproject, pr-checks.yml, and pre-commit rev, plus [tool.ruff] required-version".
**Rationale**: dependabot.yml:32 pip config groups ruff under `code-quality` (line 71) minor+patch. An automated bump PR touches only the requirements/pyproject surfaces, merges green (verified: no CI job executes the requirements-installed ruff), and desynchronizes the gate pins + required-version — recreating the disease with the enforcement pin now actively hurting (local installs from requirements-dev fail loudly).
**Alternatives considered**: remove ruff from the group but allow individual PRs (rejected: individual PRs desync surfaces identically); dependabot `versions` constraint instead of ignore (rejected: ignore-all is the honest statement that this dependency is hand-managed). Accepted tradeoff (AR#2 F7): the ignore also suppresses ruff *security* PRs; ruff is a dev/CI tool never shipped to runtime, and security bumps follow the same manual multi-surface procedure. Syntax verified: extend the pip block's existing `ignore:` list; ignore takes precedence over group membership.

## R7 — Legacy hook and black references

**Decision**: delete `scripts/pre-commit`; update README.md lines 7 (badge), 616, 694, 726, 768, 984 from the black-first workflow to the ruff/pre-commit-framework workflow; leave black pins in requirements files (out of scope, no churn by themselves).
**Rationale**: `scripts/pre-commit` self-installs via `cp` into `.git/hooks/`, runs unpinned PATH ruff, and auto-runs black — feat(057) removed black precisely because it fights ruff-format over pragma comments. Any developer who followed that README section has a hook that regenerates churn this feature exists to kill.
**Alternatives considered**: rewrite the script to pinned ruff (rejected: duplicate of the pre-commit framework, second maintenance surface); full black purge including requirements pins (rejected: widens blast radius for zero churn benefit; separate cleanup card).

## R8 — Reformat generation and atomicity

**Decision**: single commit containing all five surface edits, required-version, reformat, noqa riders, Makefile/README/dependabot/pre-commit edits, and the scripts/pre-commit deletion. Local sequence: upgrade venv ruff FIRST (0.14.11 → 0.15.14), then config edits, then `ruff format src tests` + `ruff check --fix`-free noqa placement under the pinned binary, then all gates, then GPG-signed commit.
**Rationale**: the instant required-version lands, every stale binary (venv 0.14.11, pyenv shim 0.14.13) hard-fails all ruff commands including `make validate`; an intermediate commit would strand any checkout between states. The reformat and riders MUST be produced by the pinned version so pre-commit hook output equals committed content (spec edge case).
**Alternatives considered**: two commits (pins, then reformat) (rejected: commit 1 is un-validatable locally — make validate is bricked between them); land reformat first without pins (rejected: CI lint at 0.8.4 may reject 0.15.14 formatting, and pre-commit at v0.8.4 would fight the staged files).

## R9 — In-flight dependabot ruff bump (#902 → #971)

**Decision**: close open PR **#971** (ruff 0.16.0 + pre-commit 4.6.1) as the FIRST implementation action, with a comment citing this feature; target stays 0.15.14.
**Rationale**: AR#2 (agent a2cdce5a1daa2a68d) established the live state, correcting the stale board card: #902 (0.15.14→0.15.15) was CLOSED unmerged 2026-07-27 and dependabot immediately opened #971 bumping requirements-ci/dev to 0.16.0. #971 is automerge-eligible (pr-merge.yml:149-151, semver-minor) and green — because no CI job executes the requirements-installed ruff, the spec's own blind-spot finding. If it merged, surfaces 1/5 silently become 0.16.0, invalidating FR-001's "verify only" rows and every 0.15.14 measurement. Race risk assessed low (#902 sat unmerged ~8 weeks under the same config), so closure is scheduled as implementation step 0 rather than an out-of-band action during the spec phase; quickstart step 0 re-verifies surfaces 1/5 before any work. After FR-009's ignore lands, dependabot regenerates the code-quality group PR without ruff (the pre-commit bump survives independently).
**Alternatives considered**: retarget the feature to 0.16.0 (rejected: moving target mid-battleplan; every verified measurement — reformat set, UP042 count, tag/hook-id facts, rider mechanics — was taken at 0.15.14 and would need full re-verification); freeze #971 by disabling automerge only (rejected: leaves a standing green PR that any maintainer might merge by hand); close immediately during spec phase (rejected: outward-facing action ahead of the Phase 2 go/no-go, and the race risk does not justify it).
