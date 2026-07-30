# Feature Specification: Ruff Bump-Forward (One Version Everywhere)

**Feature Branch**: `001-ruff-bump-forward`
**Created**: 2026-07-29
**Status**: Draft (post-AR#1)
**Input**: User description: "Unify the ruff toolchain version across all pinning surfaces to 0.15.14 and land the resulting repo-wide reformat, with structural drift prevention going forward."

## Problem Statement

The repository pins its Python linter/formatter (ruff) in five places that disagree:

| # | Surface | Current value | Role |
|---|---------|---------------|------|
| 1 | `requirements-dev.txt:36` | `ruff==0.15.14` | Local dev install |
| 2 | `pyproject.toml:46` (dev extra) | `ruff>=0.8.0` | Floating second dev surface |
| 3 | `.github/workflows/pr-checks.yml:55` | `pip install ruff==0.8.4` | CI lint job (format `--check`, `check`, S-rule scan at lines 59/62/65) — scoped to `src/ tests/` |
| 4 | `.pre-commit-config.yaml:54` | `rev: v0.8.4` | Commit gate, BOTH local and CI: pr-checks.yml:191-243 (Feature 1400) runs `pre-commit run --all-files` as a blocking PR job; the ruff hooks carry no files/exclude filter, so this gate reaches every tracked `.py` file repo-wide |
| 5 | `requirements-ci.txt:57` | `ruff==0.15.14` | CI test jobs (pr-checks.yml:92, :376; nightly-e2e.yml:45) — pip-installed but those jobs never invoke ruff |

The gating surfaces (3, 4) run **0.8.4**. The dev surfaces (1, 5) say **0.15.14**. The local venv has **0.14.11** and the pyenv shim on bare PATH resolves to a third stale binary, **0.14.13**. Measured 2026-07-29: `ruff format --check src/ tests/` under 0.15.14 reflows **69 files** (457 already formatted), meaning any contributor running current ruff locally produces formatting that CI rejects, and vice versa. This is the standing "ruff churn landmine": after every `make validate`, working-tree churn must be manually reverted.

Beyond the five pin surfaces, two additional mechanisms actively regenerate drift or churn:

- **Dependabot** (`.github/dependabot.yml:32`, pip ecosystem) groups ruff under `code-quality` (line 71) with minor+patch auto-updates. Left alone, it will bump surfaces 1/2/5 past 0.15.14 while surfaces 3/4 and the enforcement pin stay put — and such a PR merges green because no CI job ever runs the requirements-installed ruff.
- **`scripts/pre-commit`** is a self-installing legacy git hook (its own header instructs `cp scripts/pre-commit .git/hooks/pre-commit`) that runs unpinned PATH `ruff check` and auto-runs **black** to "fix" formatting — contradicting feat(057)'s black removal and regenerating exactly the churn this feature retires. README.md lines 7 (badge), 616, 694, 726, 768, 984 still reference the black-first workflow (6 lines, AR#3-verified census).

## Clarifications

### Session 2026-07-29

Self-answered under battleplan standing instruction (single user pause deferred to Phase 2 cumulative review); each answer is the recommended option with rationale recorded.

- Q: How to handle the in-flight dependabot ruff bump? (Board card cites PR #902 "stalled, merge it"; AR#2 established the live state: #902 CLOSED unmerged 2026-07-27, immediately superseded by open PR **#971** bumping requirements-ci/dev to **ruff==0.16.0** + pre-commit 4.6.1, automerge-eligible per pr-merge.yml:149-151 and green because no CI job executes the requirements-installed ruff.) → A: **Close #971 as the FIRST implementation action; target stays 0.15.14.** Merging #971 would move only surfaces 1/5 (the exact desync disease, made actively harmful once required-version lands). Precedent says the race risk is low (#902 sat unmerged ~8 weeks under the same automerge config), but implementation MUST verify surfaces 1/5 still read 0.15.14 before starting (quickstart step 0). FR-009's ignore stops dependabot regenerating a ruff PR; the pre-commit 4.6.1 bump survives in the regenerated group PR. The board card's next_action is rewritten by FR-013. A later deliberate multi-surface bump to 0.16.x can follow the new documented procedure.
- Q: Exact UP042 rider format? → A: Same-line rider on the flagged class-definition line: `class Foo(str, Enum):  # noqa: UP042 - StrEnum changes str() of serialized members` (ruff requires noqa on the reported line; short dash-separated justification follows the code; pragma comments are excluded from line-length per repo convention).
- Q: Is upgrading the pyenv shim (0.14.13) required for FR-008 acceptance? → A: **No.** The standard dev shell activates the venv, which shadows the shim; acceptance is `make validate` green with venv active. Shim upgrade is recommended best-effort and noted in quickstart, not gated.
- Q: Does this feature perform CLEANUP-BOARD.html card surgery (mirroring the semgrep feature's precedent)? → A: **Yes (FR-013).** Two cards: the "ruff version drift" card (evidence stale — cites 0.15.7 pins; append ASCII evidence clause, lane stays `track` until the implementation merges) and the "PR #902" card (next_action rewritten from "Merge it" to close-as-superseded per FR-009 policy).
- Q: Add enum-serialization lock tests for the 7 UP042 enums? → A: **Yes (FR-014).** One new unit test module asserting `str(member)` and `.value` semantics for all 7 enums, referencing the tech-debt entry. It proves the behavior-neutrality claim, satisfies the constitution's accompaniment rule with a real test instead of a documented exception, and turns any future accidental StrEnum "fix" into a red test instead of a silent serialization change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Contributor formats locally, CI accepts (Priority: P1)

A contributor runs the documented commands (`ruff format src/ tests/`, `ruff check src/ tests/`, or `make validate`) with the repo-pinned toolchain, commits through pre-commit, and pushes. Both CI gates that run ruff — the lint job and the pre-commit job — accept the result byte-for-byte. No churn, no revert dance.

**Why this priority**: This is the core defect. Every other outcome depends on the gates and the dev tool being the same version.

**Independent Test**: On a clean checkout with the pinned version installed, `ruff format --check src/ tests/` and `ruff check src/ tests/` exit 0 locally AND both the CI lint job and the CI pre-commit job pass on the same commit.

**Acceptance Scenarios**:

1. **Given** the feature branch with the reformat landed, **When** `ruff format --check --diff src/ tests/` runs under ruff 0.15.14, **Then** it exits 0 with zero files flagged.
2. **Given** the same commit, **When** the CI lint job runs (which installs the pinned version), **Then** all three ruff steps (format check, lint check, S-rule scan) pass.
3. **Given** the same commit, **When** the CI pre-commit job runs `pre-commit run --all-files` at the bumped rev, **Then** the ruff hooks pass across the whole tree — including the 15 tracked `.py` files outside `src/` and `tests/` (scripts/, interview/), which were verified already conformant under 0.15.14 on 2026-07-29.
4. **Given** a contributor stages a file formatted by ruff 0.15.14, **When** local pre-commit runs the ruff hooks, **Then** the hooks pass without modifying the file.

---

### User Story 2 - Version drift fails loudly at the tool, not silently at CI (Priority: P2)

A future contributor (or a stale venv) runs a ruff version different from the repo pin. Instead of silently producing divergent formatting that CI rejects later, the tool itself refuses to run, naming the required version. The known automated drift channels (dependabot's ruff grouping, the config header's `pre-commit autoupdate` runbook, the legacy `scripts/pre-commit` hook) are closed so the enforcement pin cannot be routinely tripped or bypassed.

**Why this priority**: The five-surface disagreement arose because nothing enforced agreement. Without structural prevention AND closure of the automation that regenerates drift, the same disagreement re-accumulates with the next ruff release.

**Independent Test**: With a deliberately wrong ruff version installed, `ruff check src/` fails immediately with a version-mismatch error rather than running.

**Acceptance Scenarios**:

1. **Given** a venv with a non-pinned ruff version, **When** any ruff command (`check` or `format`) runs against the repo, **Then** ruff exits non-zero citing the required version (via `[tool.ruff] required-version`; verified empirically: stale 0.14.11 enforces it for both subcommands, well under one second, exit 2).
2. **Given** the pinned version installed, **When** ruff runs, **Then** it proceeds normally.
3. **Given** the merged feature, **When** dependabot evaluates pip dependencies, **Then** ruff is excluded from automated version bumps (its upgrades are deliberate multi-surface operations).
4. **Given** an on-call engineer reading `.pre-commit-config.yaml`'s header after a CI/local mismatch, **When** they follow its guidance, **Then** it no longer instructs a bare `pre-commit autoupdate` (which would bump the rev past the required-version pin and brick every commit machine-wide).

---

### User Story 3 - New-version findings triaged without weakening gates (Priority: P3)

The version jump from 0.8.4 to 0.15.14 spans many releases. The complete new-finding set was measured 2026-07-29: exactly **7 findings, all UP042** ("str + Enum should be StrEnum") on `SentimentLabel`, `SentimentSource`, `Resolution`, `OHLCResolution`, `TimeRange`, `AuthType`, `AuthErrorCode` — enums that serialize to DynamoDB/JSON. Ruff marks the autofix unsafe (StrEnum changes `str()`/format semantics), so under this feature's behavior-neutrality constraint the pre-decided disposition is a targeted, justified `# noqa: UP042` on each — never a rule disable, and never the "fix" (a StrEnum migration is a separate runtime-behavior feature if ever wanted).

**Why this priority**: Necessary for the bump to land green, but it is consequence-handling, not the feature's purpose.

**Independent Test**: `ruff check src/ tests/` exits 0 under 0.15.14 with no rule removed from configuration, and every new `# noqa` added by this feature carries a rule code and justification and passes the repaired pragma audit.

**Acceptance Scenarios**:

1. **Given** the bumped toolchain, **When** `ruff check src/ tests/` runs, **Then** it exits 0 with the existing `[tool.ruff.lint]` select/ignore sets textually unchanged (verified 2026-07-29: no configured rule code is renamed or removed at 0.15.14, so no forced edits exist).
2. **Given** the repaired `make audit-pragma` target (see FR-011), **When** it runs under 0.15.14, **Then** it passes — including the 7 new UP042 suppressions and the pre-existing load-bearing S-rule noqas.
3. **Given** the CI S-rule scan (`ruff check src/ --select S`), **When** it runs under 0.15.14, **Then** it exits 0 (verified clean 2026-07-29).

---

### Edge Cases

- **Hook ids at the new rev**: `astral-sh/ruff-pre-commit` tag `v0.15.14` exists (verified via ls-remote, sha `0c7b6c98`) and its `.pre-commit-hooks.yaml` defines `ruff-check`, `ruff-format`, AND `id: ruff` as an explicit legacy alias with an identical entry. Keeping the old id would not error at this rev; renaming `ruff` → `ruff-check` is forward-hygiene (the alias may disappear in a future rev), applied together with the rev bump.
- **Rule renames/deprecations across 0.8→0.15**: verified 2026-07-29 — every explicit code in the config (E501, S101, S105, S106, S108, S110, S311, E402, C420, S202, S324, RUF100, external B108/B202/B324) resolves without warnings under 0.15.14. No forced edits; the FR-005 escape hatch exists only in case the picture shifts before implementation.
- **required-version reaches into pre-commit's isolated env**: pre-commit installs its own ruff from the rev, but that ruff still reads pyproject and enforces `required-version` (verified: mismatch → exit 2 for both `check` and `format`). Rev and required-version MUST move in lockstep forever; FR-010 removes the autoupdate runbook that would break the lockstep.
- **Atomic landing constraint**: the instant `required-version = "==0.15.14"` lands in pyproject, every stale local ruff (venv 0.14.11, pyenv shim 0.14.13) hard-fails `make validate` (Makefile uses PATH ruff). All five surface edits, the reformat, the enforcement pin, and the local-binary upgrades must land in one commit / one sitting — no intermediate state where the pin exists but the tool doesn't match.
- **Reformat vs. open branches**: the 69-file reformat will conflict with any open branch touching those files (notably `001-role-derivation-canonical`). Ordering is handled at the battleplan level (this feature merges last); noted here as known blast radius.
- **Pragma comments**: the repo relies on ruff-format preserving `# noqa` / `# nosec` / `# pragma` comments (Black was removed for this reason). The new formatter version must not strip or reflow them; the repaired pragma audit is the check.
- **`--fix` in pre-commit**: the lint hook runs with `args: [--fix]`. The committed reformat and noqa riders must be generated under the pinned version so hook output and committed content agree.
- **requirements-ci.txt already at target**: surface 5 needs no edit, but must be re-verified at implementation time so the "one version everywhere" claim holds across all five surfaces.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: All five pin surfaces MUST specify exactly ruff 0.15.14: `requirements-dev.txt` (already), `pyproject.toml` dev extra (tighten `>=0.8.0` → `==0.15.14`), `pr-checks.yml` lint-job install (bump `0.8.4` → `0.15.14`), `.pre-commit-config.yaml` (bump rev to `v0.15.14`), `requirements-ci.txt` (verify, already at target).
- **FR-002**: The repo-wide reformat produced by `ruff format` at 0.15.14 over `src/` and `tests/` MUST be committed as part of this feature, and `ruff format --check src/ tests/` MUST exit 0 afterward. The 15 tracked `.py` files outside those directories (reached by the CI pre-commit job) were verified already conformant; implementation MUST re-verify and include them in the reformat commit if the picture has shifted.
- **FR-003**: The pre-commit config MUST adopt the current hook id `ruff-check` (replacing legacy alias `ruff`) at rev `v0.15.14`, preserving the existing `args: [--fix]` behavior on the lint hook and the `ruff-format` hook unchanged in role.
- **FR-004**: `pyproject.toml` `[tool.ruff]` MUST gain `required-version = "==0.15.14"` so any non-pinned ruff invocation fails loudly at the tool (both syntaxes `"==0.15.14"` and `"0.15.14"` verified accepted; the explicit `==` form is used).
- **FR-005**: Existing `[tool.ruff]` configuration (line-length 88, select/ignore sets, per-file-ignores, isort settings) MUST remain textually unchanged, except where the new version forces a rename/removal (none known as of 2026-07-29), with any forced mapping documented.
- **FR-006**: The 7 new UP042 findings MUST each receive a same-line targeted rider on the flagged class-definition line in the form `# noqa: UP042 - <short justification>` (behavior-neutrality: StrEnum changes str()/format semantics for DynamoDB/JSON-serialized enums); any OTHER finding newly surfaced at implementation time MUST be resolved by code fix or targeted rule-coded suppression with justification. Blanket disables (removing rules from select, adding to global ignore) are prohibited.
- **FR-007**: The CI lint job's three ruff steps (format check, lint check, S-rule security scan) MUST remain present and gate at the same or stricter severity; the S-rule scan passes clean under 0.15.14 (verified 2026-07-29) and MUST still pass at implementation time.
- **FR-008**: The project venv ruff (currently 0.14.11) MUST end at 0.15.14. Acceptance: `make validate` passes on a clean tree in the standard dev shell (venv active, which shadows the stale pyenv shim at 0.14.13; upgrading the shim is recommended best-effort, not gated).
- **FR-009**: Ruff MUST be excluded from dependabot's automated pip version bumps (removed from the `code-quality` group's reach via an ignore entry in `.github/dependabot.yml`), with a comment stating that ruff upgrades are deliberate multi-surface operations. Rationale: an automated bump moves surfaces 1/2/5 while 3/4 and required-version stay, recreating drift that merges green because no CI job executes the requirements-installed ruff. Accepted tradeoff: the ignore also suppresses dependabot *security* PRs for ruff — a ruff security release likewise goes through the manual multi-surface procedure (ruff is a dev/CI tool, never shipped to runtime).
- **FR-010**: The `.pre-commit-config.yaml` header runbook (lines 17-19) MUST be updated to remove the bare `pre-commit autoupdate` instruction and instead direct engineers to the pinned-version upgrade procedure (all surfaces together), since autoupdate past the rev now bricks every commit via required-version enforcement.
- **FR-011**: The `make audit-pragma` target MUST be repaired so RUF100 evaluates against the full configured rule set (e.g. extend-select semantics instead of `--select RUF100`, which replaces the select set and falsely flags every S-rule noqa as unused — 14 false positives today under every ruff version, pre-existing). The repaired target MUST pass under 0.15.14.
- **FR-012**: The legacy self-installing hook `scripts/pre-commit` (unpinned PATH ruff + auto-run black, contradicting feat(057)) MUST be deleted, and ALL README.md black-workflow references MUST be updated to the ruff workflow: line 7 (Code style: black badge → ruff badge), 616 (`black --check src/ tests/` lint instruction), 694 (`black --version`), 726, 768 (`black src/ tests/` contribution instruction), 984. Verification: `grep -n black README.md` shows no workflow instruction or badge. The black pins in requirements files are NOT removed by this feature (no churn by themselves; candidate for a separate cleanup).
- **FR-013**: CLEANUP-BOARD.html card surgery (pure-ASCII evidence clauses, semgrep-feature precedent): (a) the "ruff version drift" card gets an evidence append correcting its stale 0.15.7 citation and pointing at this feature; lane stays `track` until the implementation merges; (b) the "PR #902" card's evidence/next_action is rewritten to the live state: #902 closed unmerged 2026-07-27, superseded by #971 (ruff 0.16.0), which this feature closes per FR-009 policy (ruff is hand-managed; any bump must move all five surfaces together). During surgery, glance at the two MASTER roll-up cards ("Dependencies & CVEs" lists "ruff #902"; "CI/CD hygiene" lists "ruff CI/dev version drift") and update their child references.
- **FR-014**: A new unit test module MUST lock the serialization semantics of the 7 UP042-flagged enums: for each, assert `str(member)` returns the `"ClassName.MEMBER"` form and `.value` returns the wire string (current str-Enum behavior), with a module docstring referencing the tech-debt registry entry. This is the behavior-neutrality proof and the tripwire against a future accidental StrEnum conversion.

### Key Entities

- **Pin surface**: a file location that names a ruff version; five exist (table above). The feature's invariant: all five agree, and the `required-version` setting enforces agreement at runtime.
- **Drift channel**: an automated mechanism that can break the invariant without human intent: dependabot grouping (closed by FR-009), autoupdate runbook (closed by FR-010), legacy script hook (closed by FR-012).
- **Reformat set**: the files reflowed by the new formatter (69 measured 2026-07-29; exact set determined at implementation time). Pure formatting; zero behavior change.
- **Triage ledger**: the new-version findings and dispositions — currently 7× UP042 → targeted noqa (pre-decided, FR-006); anything newly surfaced at implementation time gets an explicit disposition in the implementation artifacts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Across the five pin surfaces, a grep finds exactly one ruff version string (0.15.14); zero references to 0.8.4 remain in any pin surface, workflow, or pre-commit config. (Stale mentions in historical docs — docs/cleanup/validator-inventory.md, docs/cleanup-pristine/validator-inventory.md, docs/deployment/CI_CD_WORKFLOWS.md — are point-in-time inventory records, out of scope, and excluded from this criterion.)
- **SC-002**: On the merged commit, local `ruff format --check`, local `ruff check`, local pre-commit ruff hooks, the CI lint job, AND the CI pre-commit job all pass — five gates, one version, zero churn.
- **SC-003**: Running any ruff command with a mismatched version fails within one second with an actionable version message (empirically verified pre-spec with stale 0.14.11: exit 2, both subcommands).
- **SC-004**: The "ruff churn landmine" workaround (`git checkout -- src tests` after `make validate`) is retired: `make validate` on a clean tree leaves the tree clean.
- **SC-005**: Zero lint rules removed or globally ignored relative to the pre-feature configuration (verified by diffing `[tool.ruff.lint]` sections); the only new suppressions are the 7 justified UP042 noqas plus any implementation-time additions individually recorded in the triage ledger.

## Assumptions

- 0.15.14 is the target because two surfaces already pin it and it is the version the sibling toolchain features standardized on; no newer version is chased within this feature.
- `astral-sh/ruff-pre-commit` tag `v0.15.14`: VERIFIED to exist (ls-remote, sha `0c7b6c98`), with `ruff-check`/`ruff-format` hook ids and `ruff` as legacy alias.
- The 69-file reformat count is a point-in-time measurement (2026-07-29) and may shift slightly by implementation time; the requirement is "check exits 0 after reformat," not a specific file count.
- CI test jobs pip-install ruff 0.15.14 via `requirements-ci.txt` without install failures. (They never invoke ruff, so this is install-compatibility evidence only, not runtime evidence; runtime evidence comes from the local 0.15.14 runs performed for this spec.)
- Behavior-neutrality: formatting changes and triaged lint suppressions only; no runtime code-path changes are in scope (the UP042 "fix" is explicitly rejected for this reason).

## Out of Scope

- Any rule-set expansion or reduction beyond what the version bump itself forces (none known at 0.15.14).
- StrEnum migration of the 7 UP042-flagged enums (runtime behavior change; separate feature if ever wanted).
- Changes to bandit, semgrep, detect-secrets, or any other lint/SAST tool (covered by sibling features).
- Removal of black pins from requirements files and full purge of black references beyond the README workflow lines named in FR-012 (no churn generated by the pins alone; candidate for a separate cleanup card).
- Updating historical inventory documents (docs/cleanup*/validator-inventory.md, docs/deployment/CI_CD_WORKFLOWS.md) that mention old ruff versions as point-in-time records.
- Automating future ruff upgrades — drift *prevention* is in scope via required-version and drift-channel closure; upgrade *automation* is deliberately excluded (FR-009 makes ruff upgrades manual multi-surface operations).

---

## Appendix: Adversarial Review #1 (Spec) — Findings & Dispositions

Independent adversarial reviewer (agent aef0c1895ca54127c, 2026-07-29) fact-checked every citation against the live repo, installed ruff 0.8.4/0.15.14 and ran them against the tree, pulled ruff-pre-commit tags via ls-remote, and fetched hook definitions at the exact tag. Verdict: READY WITH EDITS. All 12 findings applied:

| # | Sev | Finding | Disposition |
|---|-----|---------|-------------|
| F1 | HIGH | SC-001's repo-wide grep fails on day one: stale ruff version strings in docs/cleanup/validator-inventory.md:9-10, docs/cleanup-pristine/validator-inventory.md:9, docs/deployment/CI_CD_WORKFLOWS.md:63 | SC-001 scoped to the five pin surfaces + workflows/pre-commit config; historical docs explicitly excluded and listed in Out of Scope |
| F2 | HIGH | Gate topology wrong: pre-commit is ALSO a blocking CI gate repo-wide (pr-checks.yml:191-243 runs `--all-files`; ruff hooks unfiltered); Out-of-Scope rationale "matches the CI gate's scope" false; 15 tracked .py files outside src/tests reached | Surface table row 4 corrected; US1 scenario 3 added (CI pre-commit job + the 15 outside files, verified conformant); FR-002 re-verify clause; SC-002 now counts five gates |
| F3 | MED | Hook-id rename overstated: at v0.15.14, `id: ruff` is an explicit legacy alias — keeping it errors nothing; tag v0.15.14 exists (sha 0c7b6c98) | Edge case rewritten as forward-hygiene; FR-003 keeps the rename with correct rationale; assumption upgraded to verified fact |
| F4 | MED | `make audit-pragma` fails TODAY under every ruff version: `--select RUF100` replaces the config select set, so all S-rule noqas (14) read as unused; US3's acceptance gate unsatisfiable as written | New FR-011: repair the target to extend-select semantics; US3 scenario 2 references the repaired target and records the pre-existing failure |
| F5 | MED | Complete new-finding set is 7× UP042 (str+Enum→StrEnum) on serialized enums; autofix marked unsafe (changes str() semantics); behavior-neutrality forces suppression-only | Named in US3 and FR-006 with pre-decided disposition: targeted justified noqa; StrEnum migration explicitly Out of Scope |
| F6 | MED | Dependabot (dependabot.yml:32, group code-quality:71) will re-bump ruff in surfaces 1/2/5 and merge green (no CI job runs the requirements-installed ruff), recreating drift | New FR-009: ignore entry excluding ruff from automated bumps, with rationale comment |
| F7 | MED | Config header (.pre-commit-config.yaml:17-19) instructs `pre-commit autoupdate`, which after this feature bumps rev past required-version and bricks every commit (verified: isolated-env ruff enforces required-version, exit 2) | New FR-010: replace the runbook guidance; edge case documents the lockstep invariant |
| F8 | MED | Missed churn surfaces: scripts/pre-commit legacy hook (unpinned ruff + auto-black, contradicts feat(057)); README.md:695/726/984 black-first workflow; black pins remain in requirements | New FR-012: delete the legacy hook, fix README lines; black pin removal explicitly out-of-scoped with rationale |
| F9 | LOW | Reformat count stale on its own measurement date: 69 files, not 68 | Corrected to 69 throughout |
| F10 | LOW | Third stale binary (pyenv shim 0.14.13) unaccounted; required-version bricks make validate the instant it lands until local binaries upgraded | FR-008 widened to all PATH-resolved binaries; new atomic-landing edge case; SC-003 annotated with the empirical verification |
| F11 | LOW | FR-005 "semantically unchanged" unverifiable: category-level selects auto-enroll new rules (UP042 proves it) | FR-005 reworded to "textually unchanged except forced renames"; verified no forced renames at 0.15.14 |
| F12 | LOW | "CI installs 0.15.14 without failures" oversold as compatibility evidence — those jobs never execute ruff | Assumption downgraded to install-compatibility only, with the real runtime evidence named |

Reviewer-verified facts folded in: PyPI ruff==0.15.14 exists; S-rule scan clean under 0.15.14; no configured rule code renamed/removed at 0.15.14; required-version enforced by both `check` and `format`, both syntaxes accepted, sub-second failure from stale 0.14.11.
