# Implementation Plan: waitForResponse race regression guard

**Branch**: `002-waitforresponse-lint-guard` | **Date**: 2026-07-30 | **Spec**: [spec.md](./spec.md)
**Depends on**: `001-waitforresponse-race-sweep` (must land first)

## Summary

Wire 001's committed detector, `scripts/scan-waitforresponse-race.py`, into two enforcement points
so the act-then-wait race pattern cannot be reintroduced:

1. a `repo: local` pre-commit hook, for fast local feedback on `git commit`;
2. a step in the **required** `Lint` job of `pr-checks.yml`, which is the control that can actually
   block a merge.

No new detection logic is written. The classification rule keeps exactly one definition site. The
feature’s real content is not code, it is the verification that the guard is not inert — four
verification modes against a planted violation, covering the index-state, environment, real-CI, and
job-authority axes on which guards in this repo have previously gone quiet.

## Technical Context

**Language/Version**: Python 3.13 (detector, owned by 001), YAML (pre-commit config, GitHub Actions),
GNU Make (local target, FR-014)
**Primary Dependencies**: none added. The detector must be **stdlib-only** (spec FR-005) because the
CI `Lint` job installs only `ruff==0.15.14` on top of `actions/setup-python@v7`.
**Storage**: N/A
**Testing**: verification is by planted violation and exit-code assertion, not by a unit-test suite.
There is no product code to test.
**Target Platform**: developer workstations (Linux/WSL2) and `ubuntu-latest` GitHub Actions runners
**Project Type**: repository tooling / CI configuration
**Performance Goals**: detector completes the full scan root in under 2 seconds (spec SC-010); scan
root is 48 `.ts` files on the post-001 tree (47 at `35d5f61` plus the helper 001 T004 adds). Six
files contain matches **pre-001**; the post-001 figure is not derived anywhere and is at least seven,
since 001 T004's new `helpers/search-helpers.ts` contains a `page.waitForResponse` (AR#3 G-16)
**Constraints**: no `.venv` on the CI runner; no repository settings changes; detector is owned by
001 and may only be amended through a recorded change request
**Scale/Scope**: 2 enforcement points, 1 make target, 8 board cards, 2 stale-comment corrections, 0 lines of new
detection logic

### Version surface (recorded because it is skewed)

| Surface | Pinned `pre-commit` |
|---|---|
| `requirements-dev.txt:37` | `4.6.1` |
| `requirements-ci.txt:58` | `4.6.1` |
| `.github/workflows/pr-checks.yml:218` | `4.6.0` |
| project `.venv` | `4.5.1` |

Stage-selection behaviour was confirmed identical across all three during AR#1. `stages: [pre-commit]`
is valid on all of them. Reconciling the pins is out of scope and is not carded here because it
belongs to whichever feature owns dependency pinning.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution governs the sentiment-analyzer service (ingestion, inference, admin API, secrets,
DB access). This feature changes only repository tooling configuration and a board file.

| Gate | Applicability | Status |
|---|---|---|
| Functional requirements (ingest, dedupe, sentiment, admin API) | Not touched | PASS (N/A) |
| Availability / latency / throughput NFRs | Not touched | PASS (N/A) |
| Auth on management endpoints | Not touched | PASS (N/A) |
| Secrets not in source control | No secrets introduced | PASS |
| TLS in transit | Not touched | PASS (N/A) |
| SQL injection / unsafe DB access | No DB access | PASS (N/A) |
| Log redaction | No logging changes | PASS (N/A) |

Project-level gates that do apply:

| Gate | Status |
|---|---|
| GPG-signed commits, bypass flags forbidden | Enforced by pre-commit and the global block-no-verify hook. This feature **adds** to that enforcement surface rather than weakening it. |
| No new AWS resources | PASS — none |
| Two-dashboard rule | PASS — the detector's scan root is `frontend/tests/e2e/`, the **customer** dashboard suite. 001 T001 criterion 11 already requires the script's docstring and `--help` to name that root explicitly, precisely because two existing scripts default to the admin pytest suite. This feature must not widen the root. |
| No unjustified fallback patterns | PASS — the guard has no fallback. FR-008 forbids the only one that would be tempting (treating a missing or erroring detector as a pass). |
| No silent failures | **This is the feature.** FR-008, FR-013, and FR-007's four-mode verification exist to make every failure path observable. |
| Land green first (1400 FR-007a) | PASS by construction — FR-009 forbids landing before 001, so the guard is green on arrival. |
| Never regress to decorative (1400 AR3-F2) | PASS — FR-009 forbids suppression lists, baselines, and non-gating modes. |

**Result: PASS.** No violations, no complexity deviations to track.

## Project Structure

### Documentation (this feature)

```text
specs/002-waitforresponse-lint-guard/
├── spec.md              # Stage 1 + AR#1 appendix + Clarifications appendix
├── plan.md              # this file + AR#2 appendix
├── research.md          # decision record for the three design questions
├── data-model.md        # no persistent data; documents the classification vocabulary
├── contracts/
│   └── detector-cli.md  # FR-012 interface contract against 001's script
├── tasks.md             # Stage 7 + AR#3 appendix
└── quickstart.md        # how to run and verify the guard
```

### Source Code (repository root)

```text
.pre-commit-config.yaml            # MODIFIED — one new repo:local hook
.github/workflows/pr-checks.yml    # MODIFIED — one new step in the required `Lint` job
Makefile                           # MODIFIED — target wired into `validate` (FR-014)
CLEANUP-BOARD.html                 # MODIFIED — guard card + 7 deferred-item cards
scripts/scan-waitforresponse-race.py   # OWNED BY 001 — not edited except by recorded amendment
frontend/tests/e2e/**              # NOT MODIFIED — the guard's subject, never its patient
```

**Structure decision**: this feature adds no source directory and no new script. Its entire
footprint is four configuration and documentation files. The deliberate asymmetry — a spec of
several hundred lines producing a handful of config lines — is the point: the difficulty here is
establishing that the wiring works, not writing it.

## Design Decisions

### D1 — Reuse 001's Python detector; do not write an ESLint rule

**Decision**: the guard invokes `scripts/scan-waitforresponse-race.py`.

**Rationale**: two independent reasons, either sufficient.

1. *An ESLint rule would not execute.* `npm run lint` is `next lint`
   (`frontend/package.json:9`), there is no `--dir` argument and no `eslint` block in
   `next.config.js`, so it uses `ESLINT_DEFAULT_DIRS` =
   `["app","pages","components","lib","src"]`
   (`frontend/node_modules/next/dist/lib/constants.js:246-252`). `frontend/tests/` is not in that
   list. The rule would be written, configured, committed, and never run against a target file.
2. *It would fork the classification rule.* The trigger-action token list grew from seven entries to
   thirteen during 001's AR#3, when `.evaluate(` was found live at
   `error-visibility-search.spec.ts:158`. A JavaScript copy of an evolving Python list drifts, and
   the failure mode of that drift is a detector narrower than the defect — exactly what let three
   `waitForEvent` sites hide from an earlier `waitForResponse`-only framing.

**Rejected alternative**: adopt `eslint-plugin-playwright`. It ships no rule for this pattern, and
enabling it would flag unrelated violations suite-wide. Already Out of Scope in 001's spec.

**Deferred**: editor-time feedback. Genuinely valuable and genuinely unavailable without changing
the lint invocation. Carded under FR-011(b).

### D2 — The blocking enforcement point is the `Lint` job, not the `Pre-commit Hooks` job

**Decision**: add a `run:` step to the `Lint` job in `pr-checks.yml`, in addition to the pre-commit
hook.

**Rationale**: `main`'s branch protection lists `required_status_checks.contexts` =
`["Secrets Scan", "Lint", "Run Tests", "Playwright E2E Tests"]`, with no rulesets. The `pre-commit` job's display name is
`Pre-commit Hooks` (`pr-checks.yml:192`) and is absent from that list. A guard reaching CI only
through the pre-commit config would be **advisory**: it could go red and `gh pr merge --auto
--squash`, the repo's documented merge command, would merge anyway.

This was AR#1 finding F-01 and it was the design's central defect. The original draft asserted "the
CI pre-commit job is a blocking gate" from reading the workflow file. The workflow file cannot tell
you that; only branch protection can.

**Rejected alternative**: add `Pre-commit Hooks` to the required contexts. This is the "correct"
fix in the abstract and completes 1400 FR-007 step (b), but it is a repository settings change
requiring admin rights, and it would retroactively make **every** hook in the config a merge
blocker — including `trivy-terraform`, which is documented as non-gating because 5 HIGH findings
are outstanding. Far larger blast radius than this feature. Carded as an owner decision under
FR-011(f).

**Consequence accepted**: a Playwright race scan lives in a job named `Lint`. Slightly surprising
to a reader. The step carries a comment explaining why, and correctness of the gate outranks
tidiness of job naming.

### D3 — `language: system` with a bare `python3` entry

**Decision**: the pre-commit hook uses `language: system`, `entry: python3
scripts/scan-waitforresponse-race.py`, `pass_filenames: false`, `always_run: true`,
`stages: [pre-commit]`.

**Rationale**, one clause at a time:

| Choice | Why | What it avoids |
|---|---|---|
| `language: system` | No shebang, no `chmod +x`, no wrapper script | Keeps FR-010's file allowlist honest (AR#1 F-08) |
| `python3`, not `.venv/bin/python3` | The CI `pre-commit` job installs no `.venv` (`pr-checks.yml:211-221`) | A hook that is red in CI forever, creating pressure to SKIP-list it (AR#1 F-02) |
| `pass_filenames: false` + `always_run: true` | Whole-tree scan every invocation | The `--staged-only` inertness that makes `check-false-pass-patterns` a no-op in CI |
| `stages: [pre-commit]`, stated explicitly | Modern stage name | The deprecated `commit` alias, which all installed pre-commit versions warn is scheduled for removal (AR#1 F-07) |
| Never `stages: [push]` or `[manual]` | — | `check-error-log-assertions` is `stages: [push]` and looks like a template but fires on neither `git commit` nor `pre-commit run --all-files` (AR#1 F-04) |

**Consequence**: the detector must be stdlib-only. That is a change request against 001 T001
criterion 8, recorded in `contracts/detector-cli.md` rather than applied silently.

### D4 — Verification is the deliverable

**Decision**: four verification modes (spec FR-007), each with its own success criterion.

**Rationale**: this repo contains a worked example of a guard that is present, unskipped, green, and
inert, documented by its own authors at `pr-checks.yml:236-240`. The axes on which a guard can go
quiet are: invocation mode, scan scope, hook stage, runtime environment, and whether the job it runs
in has authority. A verification pass that covers one axis licenses a false conclusion about the
other four.

Mode (c) — `python3 -I -S`, site-packages disabled — is the one most likely to be pruned as
redundant or "simplified" by a future maintainer, so its rationale and its two wrong alternatives
are stated in the spec text, the quickstart, and contract C6 as well as here. Modes (a) and (b) both
run where `.venv` is importable and therefore cannot detect a detector with a third-party
dependency.

The specific trap is worth restating because this feature fell into it once. AR#1 added mode (c) to
close its own CRITICAL and wrote it as `env -u VIRTUAL_ENV python3 …`, which does nothing: it clears
a marker variable while `.venv/bin` remains on `PATH`. AR#2 caught it. Scrubbing `PATH` instead is
also wrong here — the system interpreter is 3.12 or 3.10 on a CLAUDE.md-conformant machine, so the
test would run the wrong version and prove nothing about a 3.13 runner. `-I -S` is the only form
that keeps the right interpreter while removing the dependency set.

Mode (d) — the draft red-team PR — was added at AR#2 because modes (a) through (c) all test the
*detector* and none of them tests the *wiring*. A hook can satisfy all three and still be attached
to a job that cannot block, or guarded by an `if:` that never fires. 1400 T006 set the precedent.

## Implementation Phases

Phase ordering is dictated by one hard constraint: **nothing in Phase B may run before 001 has
landed and the detector reports `RACY 0`.** A guard verified against a tree that still holds 27
violations proves only that it can find violations, never that it can be green.

| Phase | Purpose | Gate to enter |
|---|---|---|
| **A — Precondition check** | Confirm 001 landed; run the detector under `python3 -I -S`; confirm it satisfies all six rows of `contracts/detector-cli.md` C6, **including remediation guidance** (checked here against a throwaway violation, not deferred to Phase D — AR#3 G-07); assert non-zero on a zero-file scan for both a renamed root and an empty directory; record any divergence from 001 T001. The contract is folded into 001 T001 as of `3b86d9c`, so this phase is expected to pass | 001 merged |
| **B — Local enforcement point** | Add the `repo: local` hook per D3; correct the two stale "BLOCKING gate" statements per FR-015 (tasks T005) | Phase A clean |
| **C — Blocking enforcement point** | Add the `Lint` job step with `if: always()`; add the make target and wire it into `validate` | Phase B green locally |
| **D — Adversarial verification** | Plant a violation; assert non-zero in modes (a) `git commit`, (b) `pre-commit run --all-files` on a clean index **with the failure attributed to this hook by name**, (c) `python3 -I -S`; revert and assert zero in all three; measure runtime; rename the detector and assert non-zero; assert an undecodable file under the scan root is not silently skipped | Phases B and C complete |
| **E — Real-CI verification** | Mode (d): draft red-team PR carrying the planted violation; observe the **required `Lint`** check fail; close the PR and delete the branch | Phase D clean |
| **F — Board** | Guard card plus one card per FR-011 item (a)–(g); eight cards total, `source: 002-waitforresponse-lint-guard` | Phase E evidence recorded |

Phases D and E are the only ones that can fail in an interesting way, and they are deliberately last
so that they exercise the real wiring rather than a stand-in. Phase E is separated from D because it
is the only step that leaves the local machine, needs a push, and produces evidence nobody can fake
by rerunning a local command. It follows 1400 T006's draft red-team PR precedent.

## Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | 001's delivered detector diverges from `contracts/detector-cli.md` (imports a third-party module, omits files-scanned, exits 0 on an empty scan) | **High** — the script does not exist yet; every 001 task is unchecked | Rework in Phase A; possible amendment round-trip to 001 | Contract written before wiring; Phase A is a gate, not a formality; FR-010 permits amendment with a recorded change request |
| R2 | `Lint` is removed from `main`'s required contexts | Low | The blocking enforcement point silently becomes advisory — the exact failure this design corrects | Recorded as the feature's single external Assumption; SC-008 asserts placement, and the Assumption names the condition so a future reader can re-check it |
| R3 | A future `paths:` filter is added to `pr-checks.yml`'s `pull_request` trigger | Low | The `Lint` job stops running on some PRs | Verified absent at `35d5f61` (`:18-26`); noted as an Edge Case |
| R4 | A pre-commit release removes the deprecated stage names, erroring the whole config | Low near-term, certain eventually | Every hook stops running, not just this one | This feature uses the modern name; config-wide migration carded FR-011(e) |
| R5 | `SKIP=<hook-id> git commit` bypasses the local hook | Certain — this is not closable | Local gate skipped | Structural: the required `Lint` step is not a pre-commit hook and is unaffected |
| R6 | Detector runtime grows as the suite grows, making commits sluggish | Low | Friction, then pressure to remove the hook | SC-010 sets a measured 2s budget rather than an assumption |

R1 is the dominant risk and it is a **sequencing** risk, not a technical one. It is the direct cost
of specifying 002 before 001 is implemented, which the battleplan does deliberately so that both
features can be reviewed together before either is built.

## Complexity Tracking

No constitution violations. One complexity deviation worth naming explicitly:

| Deviation | Why accepted | Simpler alternative rejected because |
|---|---|---|
| Two enforcement points invoking the same detector two different ways (pre-commit hook, workflow step) | The local hook gives fast feedback but cannot block a merge; the `Lint` step can block but gives no feedback until push | A single enforcement point in the `Lint` job alone would surrender local feedback; a single pre-commit hook alone would be advisory in CI (D2). Duplication is of *invocation*, not of *logic* — FR-002's single definition site is preserved |

---

## Adversarial Review #2

Conducted by a second independent reviewer, distinct from AR#1's, against the full artifact suite
(spec + plan + research + data-model + contracts + quickstart) cross-checked against 001's spec and
tasks. Returned **2 CRITICAL, 6 HIGH, 15 MEDIUM, 9 LOW**.

**Orchestrator re-verification.** Both CRITICAL findings were re-checked directly before acceptance.
Both confirmed, and the second turned out to be worse than reported.

| Re-checked claim | Command | Result |
|---|---|---|
| Post-001 distribution is 16/1, total 17 — not 33 | `sed -n '327,340p' 001/spec.md` | 001 SC-001 states **"RACY 0, PROMISE-FIRST 16, OTHER 1, total 17"** verbatim, with the derivation |
| `env -u VIRTUAL_ENV` does not leave the venv | `source .venv/bin/activate; env -u VIRTUAL_ENV bash -c 'command -v python3'` | `/home/…/.venv/bin/python3`, `sys.prefix` = the venv. Confirmed no-op |
| Scrubbing `PATH` is not the fix either | `env -i PATH=/usr/bin:/bin python3 --version` | **Python 3.12.3** — the wrong interpreter version, so this "fix" would test nothing about a 3.13 runner |
| `-I -S` is the correct mechanism | `python3 -I -S -c "import sys; …"` then `python3 -I -S -c "import yaml"` | 3.13.0, `site-packages` absent from `sys.path`, `import yaml` → `ModuleNotFoundError`. Correct sandbox |

### Drift findings

Spec drift here was **caused by AR#1's own fixes**, which is the drift pattern this stage exists to
catch. AR#1 renumbered and inserted requirements; the prose that cited them was not swept.

| ID | Location | Drift | Resolution |
|---|---|---|---|
| D-01, D-02 | spec Edge Cases (2 sites) | Cited `FR-004a`, an id that never existed after AR#1's renumber | → `FR-004` |
| D-03 | spec Context, failure-taxonomy paragraph | "**FR-006** verifies against all of them" — FR-006 became the failure-output requirement; the three-mode verification is FR-007. AR#1's own findings table said FR-007 while the body still said FR-006, so the fix was written into the ledger and not into the prose | → `FR-007` |
| D-04 | research R6 taxonomy | Mapped "invocation mode" to FR-004; the whole-tree property is FR-003 | → FR-003 |
| D-05 | research R6 taxonomy | Mapped "scan scope" to FR-012, whose contract table has **no scan-root row** — the axis 002 claimed to close was closed by nothing | → `contracts/detector-cli.md` C5 |
| D-06 | spec FR-013 | Cited only 001 T001 criterion 5. Exiting non-zero on an empty scan **contradicts** criterion 6's `sys.exit(0)` "otherwise" branch | Now cites 5 (extends) **and** 6 (amends) |
| D-07 | contracts C3 | Summary table listed four fields and **dropped `total`**. 001 T001 criterion 5 requires four counts including total; 001 T002 ("total 34") and T018 ("total 17") are unverifiable without it. Implementing C3 literally would have broken 001 | Summary now requires **five** numbers, with the regression noted in-line |
| D-08 | spec SC, data-model, quickstart, plan, research | "47 `.ts` files" quoted as the operating figure. 001 T004 adds `helpers/search-helpers.ts`, and the guard only ever runs post-001 (FR-009) | → **48** at the operating sites; 47 retained where explicitly labelled pre-001 |

### Cross-artifact inconsistencies

| ID | Inconsistency | Resolution |
|---|---|---|
| X-01 | **CRITICAL.** data-model and quickstart claimed post-001 `RACY 0 / PROMISE-FIRST 33 / OTHER 1`, derived as 27 converted + 6 already-correct. 001 SC-001 says **16**, total **17** | Corrected in both, with the derivation spelled out and a warning against "correcting" it back |
| X-02 | data-model's relationship diagram showed 47 files / 34 call sites with no era label, reading as steady state | → 48 files / 17 call sites, labelled post-001 |
| X-03 | 47 vs 48 across five artifacts | Resolved with D-08 |
| X-04 | "grew from **six** tokens to thirteen" in four artifacts. 001 AR#3 F-09 names the six tokens *added*, leaving a prior list of **seven** | → seven, in all four |
| X-05 | plan Scale/Scope said "~6 board cards" against SC-014's count | → 8 |
| X-06 | Clarification C2's card-key list omitted `milestone`, present on 3 of 118 cards, while claiming to be the observed vocabulary | Noted; C2's list is descriptive, and the eighth key is now acknowledged |
| X-07 | SC-002 decided on `git commit` but quickstart's mode (a) ran `pre-commit run`, so the criterion had no procedure | quickstart mode (a) now runs `git commit -S` |

### New findings

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| N-01 | **CRITICAL** | **FR-007 mode (c) was a no-op.** `env -u VIRTUAL_ENV python3 …` clears a marker variable while `.venv/bin` stays on `PATH`, so `python3` still resolved inside the venv. Mode (c) was the fix AR#1 added to close its own CRITICAL F-03, and it collapsed straight back into the environment it was meant to escape — on the default shell CLAUDE.md prescribes | Mode (c) is now `python3 -I -S`, which keeps 3.13 while removing site-packages. The mechanism and the two wrong alternatives are written into FR-007, quickstart, and contract C6 so it cannot be "simplified" back. New **SC-005** makes it a standing check rather than a one-time gate |
| N-02 | HIGH | FR-006 (remediation guidance in output) and FR-012 (stdout stream) are requirements against 001's deliverable that no 001 criterion covers, yet Clarification C5 asserted "**two** amendments are already filed" | Two further amendment blocks added to contract C3. The ledger now reads four, plus 001 T001 criterion 9's intentional inversion |
| N-03 | HIGH | `.pre-commit-config.yaml:190-192` still says the pre-commit job runs hooks "as a **BLOCKING** gate", and `pr-checks.yml:229` names the step "Run pre-commit (blocking)". **That sentence is what this feature's own Stage 1 draft read and repeated**, producing AR#1's CRITICAL F-01. The new hook lands a few lines below it | Promoted to **FR-015** rather than carded. Both files are already in the FR-010 allowlist; leaving the false claim next to a hook that depends on the opposite fact guarantees the next reader repeats F-01 |
| N-04 | MEDIUM | `scripts/` is outside every **required** CI check — `Lint` runs ruff over `src/ tests/` only, bandit is `-r src/`, `make lint` is `src tests`. 002 promotes a `scripts/` file into the required merge path with no required check covering it | Carded FR-011(g) |
| N-05 | MEDIUM | Nothing enforced FR-005 (stdlib-only) past a one-time Phase A inspection | New **SC-005**: `python3 -I -S …` exits 0 on a clean tree, failing the moment a third-party import appears |
| N-06 | MEDIUM | The `Lint` step is placed last (C4) and Actions steps are fail-fast, so any ruff failure meant the guard never ran and produced no output | FR-004 now requires `if: always()`, with the reasoning stated |
| N-07 | MEDIUM | SC-007's `specs/` exclusion was justified by `001/tasks.md:61-63` — a **Markdown** file the command's `--include` filters cannot reach. The exclusion is genuinely needed, for a different reason | Rewritten (now SC-009) to name the real hazard: `specs/` holds real `.ts` and `.yaml` files matching the filters |
| N-08 | MEDIUM | SC-007 asserted "exactly one definition site" but counted grep **lines**. Any correct implementation holds the tokens in both the docstring (001 T001 criterion 3 requires them verbatim) and an executable list, returning ≥2 — a criterion that reads as failure on a correct build, which is 001's own CX-4 trap reproduced | Now counts **files** via `cut -d: -f1 \| sort -u \| wc -l` → 1 |
| N-09 | MEDIUM | FR-014 was conditional ("if a make target is added") while C1 and plan Phase C made it mandatory, and no SC covered it | FR-014 made unconditional; new **SC-013** asserts `make validate` fails on a planted violation and that the target is on the `validate` dependency line |
| N-10 | MEDIUM | FR-008 had no success criterion — "a missing detector must not read as a pass" was asserted by construction and checked by nobody | New **SC-012**: rename the detector, assert both enforcement points exit non-zero |
| N-11 | MEDIUM | SC-010's "locatable by grep" specified no pattern, so it was satisfiable by any cards or none | Now **SC-014**: count cards whose `source` is `002-waitforresponse-lint-guard`, expect exactly 8 |
| N-12 | MEDIUM | The fork-PR edge case concluded "no gap here today" having checked only for `paths:` filters. `pull_request` builds the fork's checkout, so a fork can edit the detector or delete the step from its copy of the workflow | Conclusion narrowed to what was checked; the fork-edits-the-detector case recorded as a review-mitigated residual |
| N-13 | LOW | SC-006 named no command despite the section preamble promising one for each | Now **SC-008**, with an explicit grep |
| N-14 | LOW | Contract C1 assumed `python3` is 3.13 everywhere; CLAUDE.md documents system Python as 3.10 and the symlink as apt-resettable | ~~Resolved by N-01's `-I -S`~~ — **REOPENED AND PROPERLY RESOLVED at AR#3 (G-04)**. `-I -S` is verification mode (c), a manual command. The hook entry is `python3 scripts/...`, which resolves from the committing shell's `PATH` and was never addressed. Empirically: with the venv off `PATH`, `python3` here is **3.12.3**. Now closed by a new **001 T001 criterion 13** — an in-script `sys.version_info >= (3, 13)` floor that exits non-zero with the required version. This entry is left struck through rather than rewritten, because a resolution that names a real fix and applies it to the wrong mechanism is the failure mode this ledger exists to catch |
| N-15 | LOW | quickstart hardcoded an absolute path | → `cd "$(git rev-parse --show-toplevel)"` |
| N-16 | LOW | quickstart's bare `git reset` unstages the developer's whole index | → `git restore --staged <file>` |
| N-17 | LOW | Mode (b) works only because `pass_filenames: false` plus a filesystem-walking detector catches an untracked file; undocumented and load-bearing | Added as a row in contract C6 ("ignores any file list") with the SC-003 consequence stated |
| N-18 | LOW | 001 T001 criterion 9 is permanently inverted by this feature and was absent from the amendment ledger | Added, marked as an intentional inversion |

### SC renumbering

Resolving N-05, N-09, N-10 and promoting the CI check inserted new criteria mid-sequence. The
Success Criteria section went from 11 entries to 15. Mapping, for anyone reading AR#1's ledger,
whose SC references are preserved as the historical record of what AR#1 said at the time:

| AR#1 numbering | Current |
|---|---|
| SC-001 – SC-004 | unchanged in meaning; SC-004 now specifies `-I -S` |
| SC-005 (wiring grep) | SC-007 |
| SC-006 (`SKIP` placement) | SC-008 |
| SC-007 (token single-source) | SC-009 |
| SC-008 (runtime budget) | SC-010 |
| SC-009 (scan-root rename) | SC-011 |
| SC-010 (board cards) | SC-014 |
| SC-011 (file allowlist) | SC-015 |
| — | SC-005 (durable stdlib-only), SC-006 (real-CI check), SC-012 (detector rename), SC-013 (`make validate`) are new |

### Scope-definition lesson

AR#1 closed its self-defeat check by claiming the residual risk was "concentrated in one external
condition rather than in the design". AR#2 falsified that twice over. The verification mode AR#1
added to close its own CRITICAL did not work (N-01), and the arithmetic AR#1 never examined was
wrong by 17 (X-01).

The generalisable point is that **a review's fixes are not self-verifying**. AR#1 changed a design,
renumbered a requirement set, and asserted a resolution for each finding; six of those resolutions
were incompletely applied (D-01 through D-06) and one was applied in a form that did not do what it
said (N-01). The AR#2 stage earns its place not by finding new categories of defect but by checking
whether the previous stage's repairs actually landed.

### Gate

All CRITICAL and HIGH findings resolved, with both CRITICALs re-verified by the orchestrator against
live command output rather than accepted from the reviewer's summary. Every MEDIUM was resolved or
carded; every LOW was resolved.

Design changes at this gate: verification grew from three modes to four (adding the real-CI draft PR,
1400 T006's precedent); mode (c) changed mechanism entirely; the contract gained a fifth summary
number and two more filed amendments; FR-014 became unconditional; FR-015 was added to correct the
stale claim that misled this feature's own first draft.

**0 CRITICAL, 0 HIGH remaining.**

---

## Plan Second Pass (Stage 6)

Run because AR#2 found drift requiring realignment. This stage is not a re-plan from scratch; it is
a sweep for artifact text that still described the pre-AR#2 design after the findings were resolved.

**Realignment applied to this file:**

| Location | Was | Now |
|---|---|---|
| Summary | "three invocation modes … index-state, environment, and job-authority axes" | four verification modes, adding the real-CI axis |
| Technical Context | "GNU Make (optional local target)"; scan root "47 `.ts` files" | make target is required by FR-014; 48 files post-001 |
| Scale/Scope | "1 optional make target, ~6 board cards" | 1 make target, 8 board cards, 2 stale-comment corrections |
| Constitution Check | "FR-007's three-mode verification" | four-mode |
| Project Structure | "optional target"; "6 deferred-item cards" | target wired into `validate` (FR-014); 7 deferred-item cards |
| D1 | token list "grew from six entries" | seven entries (AR#2 X-04) |
| D4 | "three verification modes"; mode (c) described as "clean environment, no `.venv`" | four modes; mode (c) restated as `python3 -I -S` with both wrong alternatives named, plus mode (d)'s rationale |
| Implementation Phases | five phases A–E; Phase D asserted "all three modes" | six phases A–F; D splits local verification from E's real-CI draft PR; C gains `if: always()` and FR-015 |
| Risk R2, R6 | cited SC-006, SC-008 | SC-008, SC-010 after the AR#2 renumber |

**Realignment applied to sibling artifacts** (recorded here because Stage 6 owns the sweep):

- `spec.md` — US2 acceptance scenario 3 rewritten from "no `.venv` and no project dependencies …
  bare Python 3.13 interpreter" to the `-I -S` form, and a new scenario 4 added for the real-CI mode.
  Two dangling `FR-004a` references corrected. One `FR-006` → `FR-007` in the Context taxonomy.
- `research.md` — R6's failure-taxonomy table remapped: "invocation mode" now points at FR-003 (the
  whole-tree property) rather than FR-004, and "scan scope" at `contracts/detector-cli.md` C5 rather
  than FR-012, whose contract table has no scan-root row.
- `data-model.md` — post-001 distribution corrected to `RACY 0 / PROMISE-FIRST 16 / OTHER 1`, total
  17, with the derivation; relationship diagram relabelled to the post-001 steady state.
- `contracts/detector-cli.md` — summary requirement raised from four numbers to five (`total`
  restored); two further amendments filed; C6's dynamic check changed to `-I -S`.
- `quickstart.md` — expected output corrected to 16/17/48 with an explicit warning not to "correct"
  it back; mode (a) now runs `git commit`; mode (c) changed to `-I -S`; a new section 2b for the
  draft red-team PR.

**Constitution re-check after design changes: still PASS.** The additions (FR-014 mandatory make
target, FR-015 comment corrections, mode (d) draft PR) touch no constitution gate. FR-015 edits two
files already inside FR-010's allowlist. Mode (d) pushes a temporary branch and opens a draft PR,
which is a process step rather than a repository change, and Phase E requires the branch be deleted
and the PR closed.

**No new complexity deviations.** The single tracked deviation (two enforcement points invoking one
detector) is unchanged.
