# Implementation Plan: Ruff Bump-Forward (One Version Everywhere)

**Branch**: `001-ruff-bump-forward` | **Date**: 2026-07-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-ruff-bump-forward/spec.md`

## Summary

Unify ruff at 0.15.14 across the five pin surfaces, land the 69-file reformat of `src/` and `tests/`, suppress the 7 new UP042 findings with justified noqas, add `required-version` enforcement, and close the three automated drift/churn channels (dependabot grouping, autoupdate runbook, legacy `scripts/pre-commit` hook). Behavior-neutral by construction: formatting + config + suppressions only; zero runtime code-path changes.

## Technical Context

**Language/Version**: Python 3.13 (tooling target; no runtime code changes). Config formats: pip requirements, TOML, YAML (GitHub Actions + pre-commit), Make, Markdown (README surgery).
**Primary Dependencies**: ruff 0.15.14 (PyPI, verified exists); astral-sh/ruff-pre-commit tag `v0.15.14` (verified, sha `0c7b6c98`, hook ids `ruff-check`/`ruff-format` with `ruff` as legacy alias).
**Storage**: N/A (toolchain configuration only).
**Testing**: The gates themselves are the tests — local `ruff format --check` / `ruff check`, repaired `make audit-pragma`, pre-commit run, CI lint job + CI pre-commit job. Existing pytest suite must stay green (reformat is behavior-neutral; verified by running unit tests post-reformat).
**Target Platform**: Developer workstations (WSL2/Linux), GitHub Actions ubuntu runners.
**Project Type**: Single repo, tooling-configuration feature.
**Performance Goals**: `required-version` mismatch fails in <1s (verified empirically pre-spec). No CI duration regression beyond ruff install size delta.
**Constraints**: Atomic landing — all five surface edits + reformat + noqas + enforcement pin + local binary upgrades in ONE commit (no intermediate state where the pin exists but tools mismatch). Merge-ordering: this feature lands LAST of the three toolchain features (69-file blast radius), then `001-role-derivation-canonical` rebases immediately.
**Scale/Scope**: 5 pin surfaces, 69 reformat files, 7 noqa riders, 3 drift-channel closures, 1 Makefile recipe line, 6 README black references (incl. badge), 1 file deletion, 2 board-card edits + MASTER roll-up touch-ups (FR-013), 1 new unit test module (FR-014 serialization lock), 1 GitHub PR closure (#971 — live successor of closed #902, per clarify Q1/R9).

## Constitution Check

*GATE: evaluated against constitution v1.6.*

| Constitution clause | Impact | Verdict |
|---|---|---|
| §8 Pre-Push Requirements (lint + format + GPG + feature branch) | Feature strengthens this exact clause: gates and dev tool converge on one version | PASS |
| §8 Pipeline Check Bypass (never bypass) | No gate weakened; lint job steps preserved at same-or-stricter severity (FR-007) | PASS |
| §10 Local SAST (bandit pre-commit + semgrep in make validate) | Untouched. FR-011 repairs `audit-pragma` (a pragma-validity check), not `sast`. Bandit invocations byte-identical | PASS |
| §9 Tech Debt Tracking ("noqa comments" are registry-triggering workarounds) | The 7 UP042 suppressions REQUIRE a `docs/reference/TECH_DEBT_REGISTRY.md` entry (root cause: unsafe autofix vs behavior-neutrality; proposed fix: StrEnum migration feature). NOTE: constitution §9 cites the stale flat path `docs/TECH_DEBT_REGISTRY.md`; the real registry lives under docs/reference/ (AR#2 F3) | PASS with obligation → carried into tasks |
| §7 Implementation Accompaniment Rule (new code needs unit tests) | FR-014's enum-serialization lock tests are the accompaniment (added at clarify); remaining changes are config, covered by the gates themselves | PASS |
| Constitution §5 CI/CD mentions tfsec/tflint (line 68) | Pre-existing falsehood, owned by Feature 1 (tfsec removal) Phase 2 item; NOT this feature's scope | NOTED, no action |

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-ruff-bump-forward/
├── spec.md              # Done (post-AR#1)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (change-surface inventory)
├── quickstart.md        # Phase 1 output (implementation-day runbook)
├── checklists/requirements.md
└── tasks.md             # /speckit.tasks output (not created by plan)
```

`contracts/` is intentionally omitted: the feature exposes no API, CLI, or library interface. Its externally observable contract is gate behavior, specified in spec.md acceptance scenarios.

### Source Code (repository root) — change surface

```text
requirements-dev.txt          # :36 already ==0.15.14 (verify only)
requirements-ci.txt           # :57 already ==0.15.14 (verify only)
pyproject.toml                # :46 dev extra >=0.8.0 → ==0.15.14; [tool.ruff] + required-version
.github/workflows/pr-checks.yml   # :55 pip install ruff==0.8.4 → ==0.15.14
.github/dependabot.yml        # ignore entry for ruff (FR-009)
.pre-commit-config.yaml       # :54 rev v0.8.4 → v0.15.14; :56 id ruff → ruff-check; :17-19 runbook rewrite
Makefile                      # audit-pragma recipe: --select RUF100 → --extend-select RUF100
scripts/pre-commit            # DELETE (legacy hook: unpinned ruff + auto-black)
README.md                     # :7/:616/:694/:726/:768/:984 black refs → ruff workflow
docs/reference/TECH_DEBT_REGISTRY.md  # TD entry for 7 UP042 suppressions (next sequential TD number;
                              # NOTE constitution §9 cites stale flat path docs/TECH_DEBT_REGISTRY.md — repo reality wins)
CLEANUP-BOARD.html            # FR-013: ruff-drift card evidence append; PR #902 card rewrite to live
                              # state (#971 successor); MASTER roll-up child-reference touch-ups
tests/unit/                   # FR-014: new enum-serialization lock test module
src/**, tests/**              # 69-file reformat + 7 noqa: UP042 riders (enum class lines)
.venv                         # pip install ruff==0.15.14 (FR-008, not committed)
(GitHub)                      # close PR #971 (ruff 0.16.0, automerge-eligible) as first implementation
                              # action (R9); verify surfaces 1/5 still 0.15.14 before starting
```

**Structure Decision**: flat config-surgery across existing files; no new modules or directories.

## Design Decisions (Phase 0 summary — full detail in research.md)

1. **Pin syntax**: `required-version = "==0.15.14"` under `[tool.ruff]` (explicit `==` form; both syntaxes verified accepted).
2. **Hook ids**: adopt `ruff-check` (drop legacy alias `ruff`) at rev `v0.15.14`, keep `args: [--fix]` and `ruff-format` unchanged.
3. **UP042 disposition**: 7× `# noqa: UP042` placed on the class-definition line of each flagged enum, each with a short justification comment; StrEnum migration explicitly rejected (unsafe autofix — changes `str()`/format semantics for DynamoDB/JSON-serialized values).
4. **audit-pragma repair**: `--select RUF100` → `--extend-select RUF100` (evaluates RUF100 against the full configured rule set instead of replacing it; kills the 14 pre-existing false positives; robust even if RUF100 ever leaves the config select list).
5. **Dependabot closure**: `ignore` entry for `ruff` (all update types) in the pip ecosystem block, with a rationale comment; keeps the `code-quality` group for other tools.
6. **Runbook rewrite**: `.pre-commit-config.yaml` header steps no longer suggest `pre-commit autoupdate`; new guidance points to the multi-surface pinned-upgrade procedure (all five surfaces + required-version + reformat together).
7. **Legacy hook**: delete `scripts/pre-commit` outright (superseded by the pre-commit framework since feat(057); its auto-black behavior actively regenerates churn). README references updated to `pre-commit install`.
8. **Ordering inside the single commit** (atomicity per spec edge case): venv upgrade first (local), then config edits, then reformat + noqas generated BY the pinned binary, then gates run, then commit. The pyenv shim is upgraded or bypassed (venv activation shadows it); FR-008 acceptance is `make validate` green in the standard dev shell.

## Phase 1 Artifacts

- **data-model.md**: change-surface inventory as entities (pin surfaces, drift channels, reformat set, triage ledger) with before/after values and verification method per row.
- **quickstart.md**: implementation-day runbook in exact execution order with checkpoint commands, including the RUFF CHURN LANDMINE retirement note (the standing `git checkout -- src tests` workaround becomes obsolete AT this commit, not before).

## Post-Design Constitution Re-Check

Unchanged from initial check: PASS on all gates; the §9 tech-debt obligation (UP042 registry entry, correct docs/reference/ path) is carried as an explicit task. No complexity deviations.

---

## Appendix: Adversarial Review #2 (Plan) — Findings & Dispositions

Independent adversarial reviewer (agent a2cdce5a1daa2a68d, 2026-07-29) attacked the plan layer empirically: scratch venv with ruff 0.15.14, rider-mechanics experiments against repo config, full-tree format/check runs on a temp copy, enum semantics on repo Python 3.13.0, gh CLI against live GitHub state, full unit suite run (4061 passed, 97s). Verdict: READY WITH EDITS. All 8 findings applied:

| # | Sev | Finding | Disposition |
|---|-----|---------|-------------|
| F1 | HIGH | Board card stale: PR #902 CLOSED unmerged 2026-07-27; live successor #971 bumps ruff to 0.16.0, automerge-eligible (pr-merge.yml:149-151), green because no CI job runs requirements-installed ruff — could invalidate the feature's premise | Clarify Q1, R9, FR-013(b) rewritten to live state; #971 closure is the FIRST implementation action; quickstart step 0 verifies surfaces 1/5 still 0.15.14 with a STOP branch; flagged for the Phase 2 go/no-go summary |
| F2 | HIGH | Quickstart omitted three deliverables (FR-013 board surgery, FR-014 test module, PR closure); step 6 staging range excluded them structurally | New step 4 "Companion deliverables" before the gates; step 6 staging list includes them |
| F3 | MED | `docs/TECH_DEBT_REGISTRY.md` does not exist; real registry is `docs/reference/TECH_DEBT_REGISTRY.md` (constitution §9 carries the same stale flat path) | Path corrected in plan/data-model/quickstart; constitution stale path NOTED alongside the tfsec row |
| F4 | MED | FR-012's README list incomplete/off-by-one: black references at 7 (badge), 616, 694, 726, 768, 984 — data-model's grep verification would fail as written | FR-012, data-model row, quickstart 2.7 extended to all six; badge replaced with ruff badge |
| F5 | LOW | Hardcoded line anchors (requirements-dev:36, pyproject:46) guaranteed to drift — semgrep feature merges first and edits the same blocks | Anchor-drift note added to quickstart header; step 2 references content anchors |
| F6 | LOW | "Clean tree" precondition unsatisfiable: spec artifacts uncommitted on a zero-commit branch | Step 0 clarified: spec artifacts belong to the stage-9 docs commit, nothing else outstanding |
| F7 | LOW | FR-009 ignore-all also suppresses dependabot security PRs for ruff — unstated tradeoff | Accepted-tradeoff sentence added to FR-009 and R6 (ruff is dev/CI-only, never shipped to runtime) |
| F8 | LOW | Manual file enumeration at commit invites a silently incomplete commit (commit-time hooks only see staged files) | Step 6 uses `git add -u src tests` + named config/doc files + empty-status check |

Reviewer-verified design decisions that HOLD (empirical, 0.15.14): same-line `# noqa: UP042 - text` riders suppress UP042, count as USED under `--extend-select RUF100`, and survive `ruff format` untouched; repo precedent for dash-justification noqa at tests/unit/test_sentiment.py:883. Enum semantics on Python 3.13.0: `str(member)` == `"Foo.BAR"`, `f"{member}"` == `"Foo.BAR"`, `.value` == wire string; none of the 7 defines `__str__`/`__format__`. Counts: 7 UP042 pre-format, 69 reformat / 457 clean, zero lint delta post-format, format idempotent, S-scan clean, broken audit-pragma = exactly 14 false positives → 0 repaired. Zero overlap between reformat set and .secrets.baseline's 77 files (no baseline churn). make validate chain (`fmt lint security sast check-banned-terms check-test-target-headers`) contains no black and no ruff outside src tests → SC-004 holds. The 15 outside .py files are format- and check-clean (CI pre-commit job safe). Installed git hook is the pre-commit framework shim reading working-tree config → commit-time hooks run at the new rev (no stale-env atomicity hole). `scripts/pre-commit` has zero external references (delete safe). Dependabot ignore syntax verified (extend existing pip `ignore:` list; ignore precedes group membership).
