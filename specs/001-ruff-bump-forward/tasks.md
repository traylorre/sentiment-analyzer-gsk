# Tasks: Ruff Bump-Forward (One Version Everywhere)

**Input**: Design documents from `/specs/001-ruff-bump-forward/`
**Prerequisites**: plan.md, spec.md (FR-001..FR-014), research.md (R1-R9), data-model.md, quickstart.md

**Organization**: Tasks follow the quickstart's strict execution order. The entire implementation lands in ONE atomic GPG-signed commit (R8) — phases below are execution sequence within a single sitting, not merge increments. Story labels map to spec user stories: US1 = contributor formats/CI accepts, US2 = drift fails loudly, US3 = findings triaged without weakening gates.

**Tests**: FR-014 explicitly requires the enum-serialization lock test module (constitution §7 accompaniment); no other new tests — the gates themselves are the acceptance instruments.

## Phase 1: Setup & Preconditions

- [ ] T001 Verify preconditions per quickstart step 0: venv active, Python 3.13.x, `git status --short` shows nothing beyond the docs commit's contents (spec artifacts + the CLAUDE.md agent-context update, both committed at stage 9), and `grep -n "ruff==" requirements-dev.txt requirements-ci.txt` shows BOTH at 0.15.14. If either surface reads 0.16.0, STOP (PR #971 merged — re-run the empirical sweep before proceeding; see quickstart failure modes).
- [ ] T002 Close in-flight dependabot PR #971 (ruff 0.16.0 + pre-commit 4.6.1, successor of closed #902) via `gh pr close 971 --comment` citing specs/001-ruff-bump-forward and FR-009 policy (ruff is hand-managed; bumps move all five surfaces together). Verify `gh pr view 971 --json state` → CLOSED.
- [ ] T003 Upgrade venv binary FIRST: `pip install ruff==0.15.14`; verify `ruff --version` prints 0.15.14 (venv shadows the stale pyenv shim per FR-008).

## Phase 2: Foundational — config surgery (blocks all stories; no reformat yet)

- [ ] T004 In pyproject.toml: tighten dev extra `"ruff>=0.8.0",` → `"ruff==0.15.14",` AND add `required-version = "==0.15.14"` to the `[tool.ruff]` block (keep line-length 88 and all `[tool.ruff.lint]` content textually unchanged per FR-005). Anchor by content, not line number (semgrep feature shifts this file).
- [ ] T005 [P] In .github/workflows/pr-checks.yml lint job (line ~55): `pip install ruff==0.8.4` → `pip install ruff==0.15.14` (FR-001; the three ruff steps at ~59/62/65 stay untouched per FR-007).
- [ ] T006 [P] In .pre-commit-config.yaml: `rev: v0.8.4` → `rev: v0.15.14` (verified tag, sha 0c7b6c98); hook `- id: ruff` → `- id: ruff-check` keeping `args: [--fix]`; `ruff-format` unchanged (FR-003). Rewrite the header runbook (autoupdate instruction at line 18, block 16-20) to direct engineers to the multi-surface pinned-upgrade procedure instead of bare `pre-commit autoupdate` (FR-010 — autoupdate past the rev now bricks every commit via required-version).
- [ ] T007 [P] In .github/dependabot.yml pip block: extend the existing `ignore:` list with a `dependency-name: ruff` entry covering all update types + rationale comment ("ruff upgrades are deliberate multi-surface operations, see specs/001-ruff-bump-forward"; ignore precedes group membership; accepted tradeoff: also suppresses ruff security PRs — FR-009).
- [ ] T008 [P] In Makefile audit-pragma recipe: `ruff check --select RUF100 src/ tests/` → `ruff check --extend-select RUF100 src/ tests/` (FR-011 — kills the 14 pre-existing false positives caused by `--select` replacing the config select set; bandit half byte-identical).
- [ ] T009 [P] `git rm scripts/pre-commit` (zero external references, verified) and update ALL six README.md black references per FR-012: line 7 Code-style badge → ruff badge, 616 `black --check` lint instruction, 694 `black --version`, 726, 768 `black src/ tests/` contribution instruction, 984. Verify `grep -n black README.md` shows no workflow instruction or badge.
- [ ] T010 Checkpoint: `ruff check src tests` now RUNS (0.15.14 satisfies required-version) and reports exactly 7 UP042, nothing else. Any additional finding gets an explicit FR-006 disposition recorded in the triage ledger (data-model.md) before proceeding.

## Phase 3: US1 — reformat (contributor formats locally, CI accepts)

- [ ] T011 [US1] Run `ruff format src tests` under the pinned binary (~69 files per 2026-07-29 measurement; exact count may drift). Verify `ruff format --check src tests` exits 0 and the diff is formatting-only hunks (FR-002).
- [ ] T012 [US1] Verify the 15 tracked .py files outside src/tests remain conformant: `ruff format --check` and `ruff check` on scripts/ interview/ and root .py files (they were clean at 0.15.14 on 2026-07-29; the CI pre-commit job gates them repo-wide). If any drifted, include them in the reformat commit per FR-002.

## Phase 4: US3 — triage riders, lock tests, tech debt

- [ ] T013 [US3] Add same-line riders to the 7 enum class-definition lines (FR-006 format: `class Foo(str, Enum):  # noqa: UP042 - StrEnum changes str() of serialized members`): src/lib/timeseries/models.py:17 Resolution, src/lambdas/analysis/sentiment.py:353 SentimentSource + :361 SentimentLabel, src/lambdas/shared/errors/auth_errors.py:20 AuthErrorCode, src/lambdas/shared/middleware/auth_middleware.py:27 AuthType, src/lambdas/shared/models/ohlc.py:16 TimeRange + :36 OHLCResolution (line numbers pre-reformat; re-locate by class name after T011).
- [ ] T014 [US3] Verify `ruff check src tests` exits 0 AND `ruff format --check src tests` still exits 0 (riders verified format-stable at 0.15.14 by AR#2; re-confirm on the real tree).
- [ ] T015 [P] [US3] Create the FR-014 enum-serialization lock test module in tests/unit/ (e.g. tests/unit/shared/test_enum_serialization_lock.py): for each of the 7 enums assert `str(member) == "ClassName.MEMBER"` and `member.value == <wire string>` for every member; module docstring references the TD entry from T016 and states the purpose (tripwire against accidental StrEnum conversion changing DynamoDB/JSON serialization).
- [ ] T016 [P] [US3] Add the next sequential TD entry to docs/reference/TECH_DEBT_REGISTRY.md (NOT the constitution's stale flat path): 7 UP042 suppressions; Location: the 7 class lines; Status: Acceptable; Root Cause: ruff-marked-unsafe autofix vs this feature's behavior-neutrality constraint; Proposed Fix: dedicated StrEnum migration feature with serialization test sweep; Effort/Risk filled per registry format (constitution §9).

## Phase 5: US2 — drift-enforcement verification

- [ ] T017 [US2] Negative test of required-version: from a scratch venv with a non-pinned ruff (create it fresh: `python3 -m venv /tmp/oldruff && /tmp/oldruff/bin/pip install ruff==0.14.11`), run `/tmp/oldruff/bin/`-prefixed `ruff check src/` and `ruff format --check src/` against the repo — both MUST exit 2 sub-second citing 0.15.14 (SC-003). Do not commit anything from this step.

## Phase 6: Polish — board surgery, gates, atomic commit

- [ ] T018 Board surgery in CLEANUP-BOARD.html (FR-013, pure ASCII): (a) "ruff version drift" card — append evidence clause correcting the stale 0.15.7 citation, cite specs/001-ruff-bump-forward, lane stays `track`; (b) "PR #902" card — rewrite evidence/next_action to live state (closed unmerged 2026-07-27, successor #971 closed by this feature per FR-009); (c) touch up child references in the two MASTER roll-up cards ("Dependencies & CVEs": ruff #902 entry; "CI/CD hygiene": ruff CI/dev version drift entry).
- [ ] T019 Run the gate sequence in order (quickstart step 5): `make audit-pragma` (exit 0), `pytest tests/unit/ -q` (~4061 + new lock tests green), `pre-commit run --all-files` (new rev, new hook id, whole tree), `make validate`, then `git status --short` shows no unstaged churn (SC-004 — the landmine retirement proof). Then the two census checks: SC-001 — `grep -n "ruff" requirements-dev.txt requirements-ci.txt pyproject.toml .github/workflows/pr-checks.yml .pre-commit-config.yaml | grep -E "0\.[0-9]+\.[0-9]+"` shows only 0.15.14, PLUS the two checks the version-bearing grep structurally misses (`.pre-commit-config.yaml`'s rev line contains no "ruff" substring): `grep -n "0\.8\.4" requirements-dev.txt requirements-ci.txt pyproject.toml .github/workflows/pr-checks.yml .pre-commit-config.yaml` returns nothing, and `grep -A1 "astral-sh/ruff-pre-commit" .pre-commit-config.yaml | grep "rev: v0.15.14"` matches; SC-005 — `git diff pyproject.toml` shows the `[tool.ruff.lint]` select/ignore/per-file-ignores sections untouched (only the dev extra pin and the new required-version line).
- [ ] T020 Stage and commit atomically (quickstart step 6): `git add -u src tests`, then explicitly add pyproject.toml, .github/workflows/pr-checks.yml, .github/dependabot.yml, .pre-commit-config.yaml, Makefile, README.md, CLEANUP-BOARD.html, docs/reference/TECH_DEBT_REGISTRY.md, and the new test module (scripts/pre-commit deletion already staged); verify `git status --short` is clean of surprises; single GPG-signed commit `git commit -S` (R8 atomicity — no intermediate commit may exist). EXPECTED HOOK CHURN: the detect-secrets autostage wrapper will rewrite `.secrets.baseline` at commit time (T004's required-version insertion shifts the pyproject.toml Secret Keyword entry from line 111 to 112) and auto-stage it into this commit — confirm its diff is line-number-only before accepting the commit.
- [ ] T021 Post-push: watch the PR's CI legs (`gh pr checks`) until BOTH the lint job (installs ruff==0.15.14) and the pre-commit job (rev v0.15.14, `--all-files`) pass on the pushed head — this is SC-002's owner; SC-002 is NOT satisfied by T019's local gates alone.

## Dependencies

- T001 → T002 → T003 (setup strictly ordered; T002 races automerge, do not defer)
- T003 blocks ALL of Phase 2 (required-version lands in T004; a stale binary would brick every subsequent ruff call)
- T004-T009 parallelizable among themselves ([P] where marked; T004 first is cleanest since T010's checkpoint needs it)
- T010 blocks T011 (reformat only after the 7-finding baseline is confirmed)
- T011 → T012, T013 → T014 (riders re-located post-reformat)
- T015, T016 parallel to T013/T014 (different files)
- T017 anytime after T004; T018 anytime; both before T019
- T019 → T020 (gates before commit, hard)
- T020 → T021 (post-push CI watch; SC-002 closes only when both CI legs pass)

## Implementation Strategy

Single sitting, single commit. There is no MVP-increment option: R8's atomicity constraint (required-version bricks stale binaries the instant it lands) makes partial landings actively harmful. If the sitting is interrupted after T004, either finish or `git checkout -- .` and restart from T003. Estimated wall-clock: 60-90 minutes, dominated by T019's gate sequence (~5 min runtime) and T013/T018 precision edits.

## Appendix: AR#3 Adversarial Review (implementation-readiness gate, 2026-07-29)

Independent refuter agent a377cc0dcfc98519a. Verdict: **READY WITH EDITS** — all 6 findings applied (no HIGH, no re-check round required). Every empirical claim was re-measured fresh and HELD: PR #971 still OPEN; all five pin surfaces byte-exact as documented; exactly 7 UP042 at ruff 0.15.14 (locations byte-identical to the triage ledger); exactly 69 files reformat / 457 clean; 15 non-src/tests .py files clean; tag v0.15.14 sha 0c7b6c98...; required-version negative test exits 2 sub-second on 0.14.11; audit-pragma 14 false positives under `--select`; riders suppress + format-stable; T015 lock assertions flip on StrEnum conversion (not vacuous); 4061 tests collected; board cards and TD registry (next: TD-023) locatable; FR↔task coverage 14/14 with no orphan tasks.

| # | Sev | Finding | Disposition |
|---|-----|---------|-------------|
| F1 | MED | T019's SC-001 census grep structurally misses `.pre-commit-config.yaml`'s rev line (contains no "ruff" substring) — a skipped T006 would pass the census | T019: added `grep -n "0\.8\.4"` zero-hit check + explicit rev-line match |
| F2 | MED | detect-secrets autostage wrapper rewrites `.secrets.baseline` at commit time (pyproject Secret Keyword entry shifts 111→112) — unplanned file enters the atomic commit after T019's status check | T020 + quickstart step 6: expected-churn note; confirm diff is line-number-only |
| F3 | MED | T001 precondition "nothing beyond committed spec artifacts" false against live tree (`M CLAUDE.md` unowned) — literal reading STOPs the implementer | T001 + quickstart step 0: CLAUDE.md named as part of the stage-9 docs commit |
| F4 | LOW | Stale 3-line README census (695/726/984) survived in spec.md:25, plan.md change-surface tree, research.md R7, contradicting the corrected 6-line list | All three replaced with lines 7 (badge), 616, 694, 726, 768, 984 |
| F5 | LOW | T017 referenced session-scoped scratchpad env that won't exist at implementation time | T017: fresh `/tmp/oldruff` venv creation command inlined |
| F6 | LOW | SC-002's two CI legs had no verifying task (T019 covers local gates only) | New T021: post-push `gh pr checks` watch until both CI legs pass |
