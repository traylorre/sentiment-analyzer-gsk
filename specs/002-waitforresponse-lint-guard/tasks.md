# Tasks: waitForResponse race regression guard

**Feature**: `002-waitforresponse-lint-guard` | **Branch**: `002-waitforresponse-lint-guard`
**Depends on**: `001-waitforresponse-race-sweep` — **must be merged before T001 runs**
**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/detector-cli.md](./contracts/detector-cli.md),
[quickstart.md](./quickstart.md)

---

## Ground rules

| Rule | Source | Consequence if broken |
|---|---|---|
| Nothing starts until 001 is merged and the detector reports `RACY 0` | FR-009, 1400 FR-007a | The guard is born red and either blocks every commit or ships pre-suppressed |
| The detector is owned by 001. Divergences are **amendments**, not edits | FR-010, FR-012 | 002 silently absorbs a broken interface and the guard passes for the wrong reason |
| Files this feature may modify: `.pre-commit-config.yaml`, `.github/workflows/pr-checks.yml`, `Makefile`, `CLEANUP-BOARD.html`, `specs/002-*/` | FR-010, SC-015 | Scope creep |
| The planted violation is never committed or merged | FR-007, SC-015 | A deliberate race lands in the suite |
| Every commit GPG-signed; bypass flags forbidden | CLAUDE.md | Security policy violation |
| Mode (c) is `python3 -I -S`, never `env -u VIRTUAL_ENV`, never a scrubbed `PATH` | FR-007, AR#2 N-01 | The verification that proves the guard works is itself a no-op |

**Known amendments already filed against 001 T001** (contract C1/C2/C3). Phase A confirms each;
it does not discover them:

1. stdlib-only, runnable under bare `python3` — amends criterion 8 (venv invocation)
2. report files-scanned; exit non-zero on a zero-file scan — extends criterion 5, amends criterion 6
3. remediation guidance in the failure output — extends criterion 5
4. findings on stdout — criterion 5 does not specify a stream
5. criterion 9 (`grep` returns nothing) is **intentionally inverted** by SC-007 — not a defect

---

## Phase A — Precondition gate (FR-005, FR-012, FR-013)

**Purpose**: prove the detector satisfies the contract *before* any wiring exists. Phase A is a
gate, not a formality: 002 was specified against prose, because at authoring time every 001 task was
unchecked. This is where prose meets a running program.

- [ ] **T001** Confirm 001 has landed and the tree is clean
  - **Files**: none modified
  - **Satisfies**: FR-009 precondition
  - **Acceptance criteria**:
    1. `git log --oneline -1` on `main` includes 001's sweep commit, and
       `scripts/scan-waitforresponse-race.py` exists.
    2. `git status --short` is empty.
    3. `find frontend/tests/e2e -name "*.ts" | wc -l` returns **48** (47 pre-001 plus
       `helpers/search-helpers.ts` from 001 T004). If it returns 47, 001's T004 did not land and
       this phase stops.

- [ ] **T002** Verify the detector against `contracts/detector-cli.md` C6, all six rows
  - **Files**: none modified
  - **Satisfies**: FR-005, FR-012, FR-013
  - **Acceptance criteria**:
    1. **Stdlib-only, statically**: `grep -nE '^\s*(import|from) ' scripts/scan-waitforresponse-race.py`
       lists only Python 3.13 standard-library modules.
    2. **Stdlib-only, dynamically**: `python3 -I -S scripts/scan-waitforresponse-race.py` runs and
       exits **0**.
    3. **Clean exit and counts**: `python3 scripts/scan-waitforresponse-race.py` exits 0 and reports
       `RACY 0 / PROMISE-FIRST 16 / OTHER 1`, total **17**, across **48** files scanned.

       These figures are 001's (SC-001, T018 criterion 1). **Do not adjust them to match the
       detector's output.** The naive expectation is that the total stays at 34; it does not,
       because 18 of the 27 sites become `searchAndAwaitResponse(...)` calls and stop being wait
       call sites, while the helper adds one internal wait. `34 − 18 + 1 = 17`. If the detector
       prints something else, that is a finding against 001, recorded in T003.
    4. **Five summary numbers** present: RACY, PROMISE-FIRST, OTHER, total, files scanned.
    5. **Zero-file case**: with the scan root temporarily renamed, the detector exits **non-zero**.
       Restore the root immediately afterwards and confirm `git status --short` is empty.
    6. **Ignores any file list**: invoked with arbitrary file arguments, it still scans its own root.
       This property is load-bearing for SC-003, where the planted file is untracked and
       `pre-commit run --all-files` would not pass it to the hook.
    7. **Remediation guidance**: deferred to T009, which is the first point a `RACY` finding exists
       to produce output from.

- [ ] **T003** Record contract divergences as amendments against 001 T001 (depends on T002)
  - **Files**: `specs/002-waitforresponse-lint-guard/contracts/detector-cli.md` (amendment log only)
  - **Satisfies**: FR-010's amendment clause, FR-012
  - **Acceptance criteria**:
    1. Every T002 criterion that failed is written up naming the 001 T001 criterion it contradicts,
       the observed behaviour, and the required behaviour.
    2. `scripts/scan-waitforresponse-race.py` is **not** edited by this feature. If a fix is needed,
       it is made as a change to 001 and re-verified from T002.
    3. If T002 passed in full, state that explicitly. An empty amendment log must be distinguishable
       from an unperformed check.
    4. **Blocking**: Phase B does not start while any T002 criterion is failing.

---

## Phase B — Local enforcement point (FR-003)

- [ ] **T004** Add the `scan-waitforresponse-race` hook to `.pre-commit-config.yaml`
  - **Files**: `.pre-commit-config.yaml`
  - **Satisfies**: FR-003, FR-004's `SKIP` constraint
  - **Acceptance criteria**:
    1. Added under the existing `repo: local` block, adjacent to `check-false-pass-patterns`.
    2. `id: scan-waitforresponse-race` (Clarification C3 — the id follows the detector's filename
       stem, as every other local hook does).
    3. `language: system`, `entry: python3 scripts/scan-waitforresponse-race.py`.
       **Not** `language: script` (would need a shebang and `chmod +x` on a file this feature does
       not own, AR#1 F-08). **Not** `.venv/bin/python3` (the CI runner has no venv, AR#1 F-02).
    4. `pass_filenames: false` and `always_run: true`.
    5. `stages: [pre-commit]`, stated explicitly. **Not** the deprecated `commit` alias, and
       **never** `push` or `manual`. `check-error-log-assertions` is `stages: [push]` and looks like
       a template but fires on neither `git commit` nor `pre-commit run --all-files` (AR#1 F-04).
    6. A comment records why the entry is `python3` and not the venv path, so the next maintainer
       does not "fix" it toward the `pytest` hook's form.
    7. `pre-commit run scan-waitforresponse-race --all-files` exits 0 on the clean tree.

- [ ] **T005** Correct the two stale "BLOCKING gate" statements
  - **Files**: `.pre-commit-config.yaml`, `.github/workflows/pr-checks.yml`
  - **Satisfies**: FR-015
  - **Acceptance criteria**:
    1. `.pre-commit-config.yaml:190-192` no longer claims the `pre-commit` job runs hooks "as a
       BLOCKING gate". Replacement states the verified position: the job runs on every PR to `main`,
       and is **not** among `main`'s `required_status_checks.contexts`
       (`["Secrets Scan", "Lint", "Run Tests"]`).
    2. The step name at `pr-checks.yml:229`, "Run pre-commit (blocking)", is corrected or annotated.
    3. The replacement text names how to re-check the claim
       (`gh api repos/traylorre/sentiment-analyzer-gsk/branches/main/protection`), so it can be
       falsified rather than trusted.
    4. Nothing else in either comment block is altered. The `detect-secrets` / `gitleaks` SKIP
       rationale and the `stages:[push]` NO-OP note at `:236-240` are accurate and stay.
  - **Why this is in scope**: `.pre-commit-config.yaml:190-192` is the sentence this feature's own
    Stage 1 draft read and believed, producing AR#1's CRITICAL F-01 and a design that would have
    shipped an advisory guard. T004's hook lands a few lines below it. Leaving the false claim in
    place while adding a hook that depends on the opposite fact guarantees the next reader repeats
    the error.

---

## Phase C — Blocking enforcement point (FR-004, FR-014)

- [ ] **T006** Add the guard step to the required `Lint` job
  - **Files**: `.github/workflows/pr-checks.yml`
  - **Satisfies**: FR-004
  - **Acceptance criteria**:
    1. A new step in `jobs.lint.steps`, placed **last**, after `ruff check src/ --select S`
       (Clarification C4).
    2. It is a plain `run:` step invoking `python3 scripts/scan-waitforresponse-race.py`. Not a
       `uses:`, not a `pre-commit` invocation — so the `pre-commit` job's `SKIP` env cannot reach it
       (SC-008).
    3. It carries `if: always()`. Actions steps are fail-fast, and the guard is last, so without
       this any ruff failure means the guard never runs and produces no output (AR#2 N-06). The job
       still fails; both failures surface in one run.
    4. It carries a comment explaining why a Playwright race scan lives in a job named `Lint`:
       `Lint` is one of `main`'s three required status checks and `Pre-commit Hooks` is not, so this
       is the only place the guard can actually block a merge. Without the comment, a maintainer
       tidying the job would reasonably move the step out and silently make the guard advisory.
    5. No new `pip install` is added. The job already provides Python 3.13 via
       `actions/setup-python@v7` (`pr-checks.yml:29`, `:46-50`) and the detector is stdlib-only.
    6. The `Lint` job's existing steps are unchanged.

- [ ] **T007** Add the `check-waitforresponse-race` make target and wire it into `validate`
  - **Files**: `Makefile`
  - **Satisfies**: FR-014, Clarification C1
  - **Acceptance criteria**:
    1. New target `check-waitforresponse-race` whose recipe shells out to
       `python3 scripts/scan-waitforresponse-race.py`. It duplicates no logic (FR-002).
    2. Added to the `validate` dependency list at `Makefile:42`, alongside
       `check-test-target-headers` — the existing precedent for a repo-level guard over
       `frontend/tests/e2e/`.
    3. Carries a `##` help comment, matching the style of neighbouring targets.
    4. `make check-waitforresponse-race` exits 0 on the clean tree.

---

## Phase D — Local adversarial verification (FR-006, FR-007 modes a–c, FR-008)

**Purpose**: prove the guard is not decorative. Everything before this phase is assertion.

**Nothing in this phase may be committed.** The planted violation exists only as evidence.

- [ ] **T008** Plant the violation
  - **Files**: `frontend/tests/e2e/__scratch-race.spec.ts` (temporary, never committed)
  - **Satisfies**: prerequisite for T009–T013
  - **Acceptance criteria**:
    1. Contains an act-then-wait `page.waitForResponse` whose immediately preceding line is a
       `.fill(` — the canonical `RACY` shape.
    2. Carries the `// Target: Customer Dashboard (Next.js/Amplify)` header so it does not trip
       `check-test-target-headers` and confuse the evidence with an unrelated failure.
    3. `python3 scripts/scan-waitforresponse-race.py` now reports `RACY 1` and exits 1.

- [ ] **T009** Mode (a): the local commit path refuses the commit (depends on T008)
  - **Files**: none modified
  - **Satisfies**: FR-007(a), FR-006, SC-002
  - **Acceptance criteria**:
    1. `git add frontend/tests/e2e/__scratch-race.spec.ts && git commit -S -m "..."` exits non-zero.
    2. **No commit object is created** — `git log -1` is unchanged. Asserted with `git commit`, not
       `pre-commit run`, because the commit path is what US1 promises (AR#2 X-07).
    3. Output names the planted `file:line`.
    4. Output contains a literal corrected example, matching
       `const <name>Promise = page.waitForResponse` positioned before the triggering action
       (FR-006). If it does not, that is amendment 3 from the ground rules, recorded per T003.

- [ ] **T010** Mode (b): whole-tree scan with a clean index (depends on T009)
  - **Files**: none modified
  - **Satisfies**: FR-007(b), SC-003
  - **Acceptance criteria**:
    1. `git restore --staged frontend/tests/e2e/__scratch-race.spec.ts` — unstage **only** the
       planted file, never a bare `git reset`, which would unstage unrelated work (AR#2 N-16).
    2. `git diff --cached --name-only` is empty, reproducing the CI index state.
    3. `pre-commit run --all-files` exits non-zero.
    4. This is the criterion that distinguishes the guard from `check-false-pass-patterns`, which is
       green in CI for exactly this input.

- [ ] **T011** Mode (c): site-packages-free invocation (depends on T008)
  - **Files**: none modified
  - **Satisfies**: FR-007(c), FR-005, SC-004
  - **Acceptance criteria**:
    1. `python3 -I -S scripts/scan-waitforresponse-race.py` exits non-zero.
    2. The command **must** be `-I -S`. `env -u VIRTUAL_ENV` is forbidden: it clears a marker
       variable while `.venv/bin` stays on `PATH`, so `python3` still resolves inside the venv.
       Verified: `env -u VIRTUAL_ENV bash -c 'command -v python3'` returns `.venv/bin/python3`.
    3. A scrubbed `PATH` is also forbidden: `/usr/bin/python3` is 3.12 or 3.10 on a
       CLAUDE.md-conformant machine, so it would test the wrong interpreter version.
    4. Record the interpreter actually used: `python3 -I -S -c "import sys; print(sys.version)"`
       must report **3.13.x**, matching the `Lint` job's `PYTHON_VERSION`.

- [ ] **T012** Detector-absent case (depends on T008)
  - **Files**: none modified (temporary rename only)
  - **Satisfies**: FR-008, SC-012
  - **Acceptance criteria**:
    1. With `scripts/scan-waitforresponse-race.py` temporarily renamed, `pre-commit run
       scan-waitforresponse-race --all-files` exits **non-zero**.
    2. The same rename makes the `Lint` job's command shape (`python3 scripts/...`) exit non-zero.
    3. Restore the name; `git status --short` is empty.
    4. A missing detector must never read as a pass. Without this task FR-008 is asserted by
       construction and checked by nobody.

- [ ] **T013** Revert and re-assert green (depends on T009–T012)
  - **Files**: none modified
  - **Satisfies**: FR-007, SC-001, SC-005, SC-015
  - **Acceptance criteria**:
    1. Delete `__scratch-race.spec.ts`.
    2. `pre-commit run --all-files` exits **0**.
    3. `python3 -I -S scripts/scan-waitforresponse-race.py` exits **0** (SC-005 — the durable
       stdlib-only check, which fails the moment anyone adds a third-party import).
    4. `make validate` exits 0.
    5. `git status --short` is empty and `git stash list` is empty.

- [ ] **T014** `make validate` fails on a violation (depends on T007, T013)
  - **Files**: none modified
  - **Satisfies**: FR-014, SC-013
  - **Acceptance criteria**:
    1. Re-plant the violation; `make validate` exits non-zero.
    2. `grep -n 'check-waitforresponse-race' Makefile` shows the target on the `validate` dependency
       line.
    3. Remove the violation; `make validate` exits 0; tree clean.

- [ ] **T015** Measure the scan cost (depends on T013)
  - **Files**: evidence recorded in the Execution Log below
  - **Satisfies**: SC-010
  - **Acceptance criteria**:
    1. `time python3 scripts/scan-waitforresponse-race.py`, real elapsed time recorded.
    2. Under **2 seconds**.
    3. A **measured** figure is written down. An estimate does not satisfy this: the Stage 1 draft's
       "roughly ten files" guess was wrong by ~5x against the real 47, which is why the criterion
       demands measurement.

- [ ] **T016** Single-definition-site check (depends on T013)
  - **Files**: none modified
  - **Satisfies**: FR-002, SC-009
  - **Acceptance criteria**:
    1. `grep -rn "setInputFiles" --include='*.py' --include='*.js' --include='*.ts' --include='*.yaml' . | grep -v node_modules | grep -v '^./specs/' | cut -d: -f1 | sort -u | wc -l`
       returns **1**, and that file is `scripts/scan-waitforresponse-race.py`.
    2. Count **files, not lines**. A correct implementation holds the tokens both in the module
       docstring (001 T001 criterion 3 requires them verbatim) and in an executable list, so a line
       count returns ≥2 and would read as a false failure — 001 hit the same trap with its own
       `searchAndAwaitResponse` grep (AR#2 N-08).
    3. The `specs/` exclusion is required because `specs/` holds real `.ts` and `.yaml` files the
       `--include` filters match. It is **not** for `001/tasks.md`, which is Markdown and
       unreachable by these filters.

- [ ] **T017** Wiring assertions (depends on T004, T006)
  - **Files**: none modified
  - **Satisfies**: SC-007, SC-008
  - **Acceptance criteria**:
    1. `grep -rn "scan-waitforresponse-race" .pre-commit-config.yaml .github/` returns hits in
       **both** files, inverting 001 T001 criterion 9.
    2. `grep -A3 'SKIP:' .github/workflows/pr-checks.yml | grep -c scan-waitforresponse-race`
       returns **0**.
    3. The guard's step under `jobs.lint.steps` has a `run:` key and an `if: always()` key.

---

## Phase E — Real-CI verification (FR-007 mode d)

**Purpose**: Phase D proves properties of the *detector*. Only CI proves the *wiring*. A hook can
pass every local mode and still be attached to a job that cannot block, or guarded by an `if:` that
never fires.

- [ ] **T018** Draft red-team PR (depends on Phase D complete)
  - **Files**: temporary branch only; **nothing merged**
  - **Satisfies**: FR-007(d), SC-006
  - **Acceptance criteria**:
    1. Branch `tmp/gate-red-team` carrying the planted violation, PR opened as **draft**, titled
       `DO NOT MERGE [gate red-team]`. Follows 1400 T006's precedent.
    2. `gh pr checks` shows the **`Lint`** check as **failed**.
    3. The failure output in the `Lint` job log names the planted `file:line`, confirming the step
       ran rather than the job failing for another reason.
    4. Confirm the guard step executed even though it is last: check the step's log is present.
    5. **Cleanup**: PR closed, remote branch deleted, local branch deleted. Verified with
       `gh pr list --state open` and `git branch -a`.
    6. The planted violation exists in no commit on `main` and no open branch.

---

## Phase F — Board (FR-011, US4)

- [ ] **T019** Add eight cards to `CLEANUP-BOARD.html` (depends on T018)
  - **Files**: `CLEANUP-BOARD.html`
  - **Satisfies**: FR-011, US4, SC-014
  - **Acceptance criteria**:
    1. Board count goes from **120** (118 today plus 001's two follow-up cards) to **128**.
    2. All eight carry `"source": "002-waitforresponse-lint-guard"`, matching the convention set by
       `001-lambda-log-visibility cards.md`. SC-014 counts by this field rather than by an
       unspecified grep pattern, which any eight cards or none would satisfy.
    3. Cards, with lane and severity per Clarification C2:

       | # | Subject | Lane | Severity |
       |---|---|---|---|
       | 1 | The guard itself: race regression guard landed, two enforcement points | `done` | `medium` |
       | 2 | FR-011(a) `page.waitForRequest` coverage — zero uses today, future risk | `track` | `low` |
       | 3 | FR-011(b) editor-time ESLint rule — blocked on `next lint` not reaching `frontend/tests/` | `track` | `low` |
       | 4 | FR-011(c) scan root beyond `frontend/tests/e2e/` if specs are added elsewhere | `track` | `low` |
       | 5 | FR-011(d) `check-false-pass-patterns` is inert in CI and admin-suite-scoped | `track` | `medium` |
       | 6 | FR-011(e) migrate `.pre-commit-config.yaml` off deprecated stage names | `track` | `low` |
       | 7 | FR-011(f) owner decision: add `Pre-commit Hooks` to required contexts (1400 FR-007b) | `track` | `medium` |
       | 8 | FR-011(g) `scripts/` is outside every required CI check | `track` | `low` |

    4. Card 5's evidence quotes `pr-checks.yml:236-240`, where Feature 1400 documented the no-op
       itself. 002 inherits the lesson, not the credit.
    5. Each card uses the existing key set (`title`, `lane`, `severity`, `evidence`, `citation`,
       `next_action`, `source`). Note the board also carries an eighth key, `milestone`, on 3 of 118
       cards; it is optional and not used here.
    6. `python3 -c "import json; ..."` `raw_decode` on the text after `const CARDS = ` parses
       cleanly and returns 128.

- [ ] **T020** Final scope and cleanliness check (depends on T019)
  - **Files**: none modified
  - **Satisfies**: SC-015
  - **Acceptance criteria**:
    1. `git diff --stat` against the branch point touches only: `.pre-commit-config.yaml`,
       `.github/workflows/pr-checks.yml`, `Makefile`, `CLEANUP-BOARD.html`,
       `specs/002-waitforresponse-lint-guard/**`.
    2. `scripts/scan-waitforresponse-race.py` is **unmodified** by this branch.
    3. `frontend/tests/e2e/**` is unmodified.
    4. No `__scratch-race.spec.ts` anywhere in history on this branch.
    5. All commits GPG-signed: `git log --show-signature` clean.

---

## Dependency graph

```
T001 ─► T002 ─► T003 ──┐   (Phase A gate — blocks everything)
                       │
                       ├─► T004 ─► T005          (Phase B)
                       │      │
                       │      └─► T006 ─► T007   (Phase C)
                       │                   │
                       └───────────────────┴─► T008 ─┬─► T009 ─► T010
                                                     ├─► T011
                                                     ├─► T012
                                                     └─► T013 ─┬─► T014
                                                               ├─► T015
                                                               ├─► T016
                                                               └─► T017
                                                                     │
                                                                     ▼
                                                                   T018   (Phase E, real CI)
                                                                     │
                                                                     ▼
                                                              T019 ─► T020 (Phase F)
```

**Serialisation notes.** T003 gates everything: wiring against an unverified interface is the
sequencing risk the plan rates **High**. T008 must follow T006 and T007, or Phase D would verify a
partially-wired guard and the green result would mean less than it appears. T018 must follow the
whole of Phase D, because a red-team PR is expensive and should not be spent discovering something
a local run would have caught.

**No task is parallelisable.** Every task either gates on a prior verification result or edits one
of four small files. Concurrency here buys nothing and risks two agents editing the same YAML.

---

## Requirement coverage

| Requirement | Covered by | Status |
|---|---|---|
| FR-001 (refuse locally, fail a required check) | T004, T006, T009, T018 | COVERED |
| FR-002 (single detector, no second implementation) | T004 crit. 3, T007 crit. 1, T016 | COVERED |
| FR-003 (local hook shape) | T004 (all criteria) | COVERED |
| FR-004 (`Lint` job step, `if: always()`, plain `run:`) | T006, T017 crit. 3 | COVERED |
| FR-005 (stdlib-only, bare `python3`) | T002 crit. 1–2, T011, T013 crit. 3 | COVERED |
| FR-006 (actionable failure output) | T009 crit. 3–4 | COVERED |
| FR-007 (four verification modes) | T009 (a), T010 (b), T011 (c), T018 (d) | COVERED |
| FR-008 (fail loudly on missing/erroring detector) | T012 | COVERED |
| FR-009 (land green, no suppression) | T001, T013 crit. 2 | COVERED |
| FR-010 (file allowlist, amendments not edits) | T003, T020 | COVERED |
| FR-011 (seven deferred cards) | T019 crit. 3 rows 2–8 | COVERED |
| FR-012 (detector interface contract) | T002, T003 | COVERED |
| FR-013 (files-scanned, non-zero on empty scan) | T002 crit. 4–5 | COVERED |
| FR-014 (make target wired into `validate`) | T007, T014 | COVERED |
| FR-015 (correct the stale BLOCKING claims) | T005 | COVERED |

| Success criterion | Decided by |
|---|---|
| SC-001 clean tree green, correct counts | T002 crit. 3, T013 crit. 2 |
| SC-002 `git commit` refused, names `file:line` | T009 |
| SC-003 `--all-files` on a clean index fails | T010 |
| SC-004 `-I -S` fails on a violation | T011 |
| SC-005 `-I -S` passes on a clean tree | T013 crit. 3 |
| SC-006 `Lint` required check fails on a draft PR | T018 |
| SC-007 wiring grep hits both files | T017 crit. 1 |
| SC-008 not in `SKIP`, is a `run:` step | T017 crit. 2–3 |
| SC-009 exactly one definition file | T016 |
| SC-010 runtime measured, under 2s | T015 |
| SC-011 scan-root rename exits non-zero | T002 crit. 5 |
| SC-012 detector rename exits non-zero | T012 |
| SC-013 `make validate` fails on a violation | T014 |
| SC-014 eight cards, `source` field | T019 |
| SC-015 file allowlist honoured, nothing planted committed | T013 crit. 5, T018 crit. 6, T020 |

**Every FR maps to ≥1 task. Every SC maps to exactly one deciding task.** No orphans in either
direction.

---

## Execution Log

*(populated during implementation — Phase A output, T015's measured runtime, T018's PR number and
check result, and the final board count go here)*

| Task | Date | Result | Evidence |
|---|---|---|---|
| | | | |
