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

**Detector contract: FOLDED INTO 001 BEFORE IMPLEMENTATION** (AR#3 G-01). These were originally
filed as amendments for Phase A to *discover*. AR#3 established that they were not gaps in 001 but
direct contradictions — 001 T001 criterion 6 read `sys.exit(0)` "otherwise", criterion 8 mandated
venv invocation, and 001 Clarification C4 promised the guard could wire the script in "without
modification". A 001 implementer following 001's own tasks.md would have produced a detector failing
at least three T002 criteria, discovered at the *second* task of this feature, with no task, branch,
or FR-010 allowlist entry authorising the repair.

Both features were still unimplemented, so the contract was folded into 001 at commit `3b86d9c`:

| # | Requirement | Now carried by |
|---|---|---|
| 1 | stdlib-only, runnable under bare `python3`, verified with `-I -S` | 001 T001 crit. 8 (rewritten) |
| 2 | five summary numbers including files-scanned | 001 T001 crit. 5 (extended) |
| 3 | non-zero on a zero-file scan — missing, renamed, **or empty** root | 001 T001 crit. 6 (rewritten) |
| 4 | remediation guidance in the failure output | 001 T001 crit. 5 (extended) |
| 5 | findings on **stdout** | 001 T001 crit. 5 (extended) |
| 6 | fixed scan root; file arguments ignored | 001 T001 crit. 12 (**new**) |
| 7 | in-script `sys.version_info >= (3, 13)` floor | 001 T001 crit. 13 (**new**) |

Items 6 and 7 were not in the original ledger. Item 6 was a contract C6 row backed by no 001
criterion at all (AR#3 G-06); item 7 closes AR#3 G-04. 001 C4 now records the amendment rather
than silently promising the old contract.

**Consequence for Phase A**: T002 is now expected to **pass**, and T003 is expected to record an
empty divergence log. Phase A remains a real gate — it verifies the fold-in landed rather than
assuming it — but a T002 failure now means 001 was implemented against its own written criteria
incorrectly, not that the criteria were wrong.

One item stays an inversion, not an amendment:

- 001 T001 criterion 9 (`grep -rn "scan-waitforresponse-race" .pre-commit-config.yaml .github/`
  returns nothing) is **intentionally inverted** by SC-007. Wiring the detector in is this
  feature's entire purpose. Not a defect in either feature.

---

## Phase A — Precondition gate (FR-005, FR-012, FR-013)

**Purpose**: prove the detector satisfies the contract *before* any wiring exists. Phase A is a
gate, not a formality: 002 was specified against prose, because at authoring time every 001 task was
unchecked. This is where prose meets a running program.

- [x] **T001** Confirm 001 has landed and the tree is clean
  - **Files**: none modified
  - **Satisfies**: FR-009 precondition
  - **Acceptance criteria**:
    1. `git log --oneline -1` on `main` includes 001's sweep commit, and
       `scripts/scan-waitforresponse-race.py` exists.
    2. `git status --short` is empty.
    3. `find frontend/tests/e2e -name "*.ts" | wc -l` returns **48** (47 pre-001 plus
       `helpers/search-helpers.ts` from 001 T004). If it returns 47, 001's T004 did not land and
       this phase stops.

- [x] **T002** Verify the detector against `contracts/detector-cli.md` C6, all six rows
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
    5. **Zero-file case, both shapes** (AR#3 G-08). (i) With the scan root temporarily renamed, the
       detector exits **non-zero**; restore the root immediately afterwards and confirm
       `git status --short` is empty. (ii) Pointed at an **empty temporary directory**, it also
       exits non-zero. Testing only the rename would pass a detector that raises on a missing root
       but returns 0 on an existing-but-empty one, which is the likelier real-world shape and is
       exactly what FR-013 forbids.
    6. **Ignores any file list**: invoked with arbitrary file arguments, it still scans its own root.
       This property is load-bearing for SC-003, where the planted file is untracked and
       `pre-commit run --all-files` would not pass it to the hook.
    7. **Remediation guidance, verified here** (AR#3 G-07). Plant a throwaway violation under the
       scan root, run the detector **standalone**, capture the output, delete the violation, and
       confirm `git status --short` is empty. The output must carry a literal corrected example
       matching `const <name>Promise = page.waitForResponse` positioned before the triggering
       action. This was previously deferred to T009, which sits in Phase D — *after* T004–T007 have
       landed the hook, the workflow step and the make target. Deferring it guaranteed that a
       contract requirement would be discovered after the gate whose entire purpose is to prevent
       wiring-before-verification. Nothing is wired at T002, so the check belongs here.
    8. **Gate completeness**: with criterion 7 moved in, every requirement in
       `contracts/detector-cli.md` is now observable from Phase A. Phase A is a complete contract
       gate, which is what plan Phase A claims it is.

- [x] **T003** Record contract divergences as amendments against 001 T001 (depends on T002)
  - **Files**: `specs/002-waitforresponse-lint-guard/contracts/detector-cli.md` (amendment log only)
  - **Satisfies**: FR-010's amendment clause, FR-012
  - **Acceptance criteria**:
    1. Every T002 criterion that failed is written up naming the 001 T001 criterion it contradicts,
       the observed behaviour, and the required behaviour.
    2. `scripts/scan-waitforresponse-race.py` is **not** edited by this feature. Since the contract
       is folded into 001 T001 (see the ground rules above), a T002 failure means the delivered
       script diverges from 001's own written criteria. **The repair route, which must exist before
       it is needed** (AR#3 G-01): open a branch off `main` named `fix/detector-contract-<crit>`,
       amend `scripts/scan-waitforresponse-race.py` to satisfy the 001 T001 criterion it violates,
       cite that criterion in the commit message, merge it, then re-run T002 in full. This is a
       change to 001's deliverable and is deliberately outside FR-010's allowlist, which is why it
       gets its own branch and PR rather than riding along in this feature.
    3. If T002 passed in full, state that explicitly. An empty amendment log must be distinguishable
       from an unperformed check.
    4. **Blocking**: Phase B does not start while any T002 criterion is failing.

---

## Phase B — Local enforcement point (FR-003)

- [x] **T004** Add the `scan-waitforresponse-race` hook to `.pre-commit-config.yaml`
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

- [x] **T005** Correct the two stale "BLOCKING gate" statements
  - **Files**: `.pre-commit-config.yaml`, `.github/workflows/pr-checks.yml`
  - **Satisfies**: FR-015
  - **Acceptance criteria**:
    1. The comment block in `.pre-commit-config.yaml` containing the literal text
       **"as a BLOCKING gate"** no longer claims it. Locate it by that string, not by line number:
       it sits at `:190-192` today, but T004 inserts roughly ten lines of hook YAML into the same
       file *earlier in the dependency graph*, shifting it to about `:200` before T005 runs
       (AR#3 G-10). This follows 001's own "PRE-SWEEP locators" discipline
       (`001/tasks.md:17-21`). Replacement states the verified position: the job runs on every PR to `main`,
       and is **not** among `main`'s `required_status_checks.contexts`
       (`["Secrets Scan", "Lint", "Run Tests", "Playwright E2E Tests"]`).
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

- [x] **T006** Add the guard step to the required `Lint` job
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
       `Lint` is one of `main`'s four required status checks and `Pre-commit Hooks` is not, so this
       is the only place the guard can actually block a merge. Without the comment, a maintainer
       tidying the job would reasonably move the step out and silently make the guard advisory.
    5. No new `pip install` is added. The job already provides Python 3.13 via
       `actions/setup-python@v7` (`pr-checks.yml:29`, `:46-50`) and the detector is stdlib-only.
    6. The `Lint` job's existing steps are unchanged.

- [x] **T007** Add the `check-waitforresponse-race` make target and wire it into `validate`
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

- [x] **T008** Plant the violation
  - **Files**: `frontend/tests/e2e/__scratch-race.spec.ts` (temporary, never committed)
  - **Satisfies**: prerequisite for T009–T013
  - **Acceptance criteria**:
    1. Contains an act-then-wait `page.waitForResponse` whose immediately preceding line is a
       `.fill(` — the canonical `RACY` shape.
    2. Carries the `// Target: Customer Dashboard (Next.js/Amplify)` header so it does not trip
       `check-test-target-headers` and confuse the evidence with an unrelated failure.
    3. `python3 scripts/scan-waitforresponse-race.py` now reports `RACY 1` and exits 1.

- [x] **T009** Mode (a): the local commit path refuses the commit (depends on T008)
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

- [x] **T010** Mode (b): whole-tree scan with a clean index (depends on T009)
  - **Files**: none modified
  - **Satisfies**: FR-007(b), SC-003
  - **Acceptance criteria**:
    1. `git restore --staged frontend/tests/e2e/__scratch-race.spec.ts` — unstage **only** the
       planted file, never a bare `git reset`, which would unstage unrelated work (AR#2 N-16).
    2. `git diff --cached --name-only` is empty, reproducing the CI index state.
    3. `pre-commit run --all-files` exits non-zero, **and the failure is attributable to this hook**
       (AR#3 G-03): pre-commit reports `scan-waitforresponse-race` as `Failed` **by name**, and its
       output names `frontend/tests/e2e/__scratch-race.spec.ts:<line>`. A bare non-zero exit is not
       sufficient — that config runs roughly twenty hooks including trivy, checkov, bandit and
       detect-secrets, any one of which satisfies a bare exit-code assertion while this guard sits
       inert. Shipping SC-003 in that form would reproduce this feature's own thesis defect inside
       its own verification.
    4. Isolated form as corroboration: `pre-commit run scan-waitforresponse-race --all-files` exits
       non-zero.
    5. This is the criterion that distinguishes the guard from `check-false-pass-patterns`, which is
       green in CI for exactly this input.

- [x] **T011** Mode (c): site-packages-free invocation (depends on T008)
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

- [x] **T012** Detector-absent case (depends on T008)
  - **Files**: none modified (temporary rename only)
  - **Satisfies**: FR-008, SC-012
  - **Acceptance criteria**:
    1. With `scripts/scan-waitforresponse-race.py` temporarily renamed, `pre-commit run
       scan-waitforresponse-race --all-files` exits **non-zero**.
    2. The same rename makes the `Lint` job's command shape (`python3 scripts/...`) exit non-zero.
    3. Restore the name; `git status --short` is empty.
    4. **Unreadable-file case** (AR#3 G-14). FR-008 forbids the detector catching a *scanning*
       exception and exiting 0. The rename case above only covers "detector absent". Write an
       undecodable byte sequence into a `.ts` file under the scan root, confirm the detector exits
       non-zero rather than skipping the file silently, then delete it and confirm
       `git status --short` is empty. Without this, half of FR-008 stays asserted by construction.
    5. A missing detector must never read as a pass. Without this task FR-008 is asserted by
       construction and checked by nobody.

- [x] **T013** Revert and re-assert green (depends on T009–T012)
  - **Files**: none modified
  - **Satisfies**: FR-007, SC-001, SC-005, SC-015
  - **Acceptance criteria**:
    1. Delete `__scratch-race.spec.ts`.
    2. **Pass/fail**: `pre-commit run scan-waitforresponse-race --all-files` exits **0**, and
       `make check-waitforresponse-race` exits **0**.
    3. `python3 -I -S scripts/scan-waitforresponse-race.py` exits **0** (SC-005 — the durable
       stdlib-only check, which fails the moment anyone adds a third-party import).
    4. **Advisory, not pass/fail** (AR#3 G-15): run `pre-commit run --all-files` and `make validate`
       and record the result. Neither is a criterion, because neither is a property of this feature.
       `pre-commit run --all-files` rides on trivy's daily-updating vulnerability database
       (`pr-checks.yml:187-189` documents that it can go red with no repo diff), checkov, and
       detect-secrets. `make validate` runs `fmt`, which executes `ruff format src tests` and is
       **mutating**, so "tree clean afterwards" is not a stable assertion; it also hard-requires
       semgrep on `PATH` and runs `pip-audit`. A red result here is investigated, not treated as a
       guard failure.
    5. `git status --short` is empty and `git stash list` is empty.

- [ ] **T014** `make validate` fails on a violation (depends on T007, T013) — **PARTIAL: crit 1 (attributable form) and crit 2 pass; crit 3 blocked by pre-existing `check-banned-terms` redness. See Execution Log.**
  - **Files**: none modified
  - **Satisfies**: FR-014, SC-013
  - **Acceptance criteria**:
    1. Re-plant the violation; `make validate` exits non-zero.
    2. `grep -n 'check-waitforresponse-race' Makefile` shows the target on the `validate` dependency
       line.
    3. Remove the violation; `make validate` exits 0; tree clean.

- [x] **T015** Measure the scan cost (depends on T013)
  - **Files**: evidence recorded in the Execution Log below
  - **Satisfies**: SC-010
  - **Acceptance criteria**:
    1. `time python3 scripts/scan-waitforresponse-race.py`, real elapsed time recorded.
    2. Under **2 seconds**.
    3. A **measured** figure is written down. An estimate does not satisfy this: the Stage 1 draft's
       "roughly ten files" guess was wrong by ~5x against the real 47, which is why the criterion
       demands measurement.

- [x] **T016** Single-definition-site check (depends on T013)
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

- [x] **T017** Wiring assertions (depends on T004, T006)
  - **Files**: none modified
  - **Satisfies**: SC-007, SC-008
  - **Acceptance criteria**:
    1. `grep -rn "scan-waitforresponse-race" .pre-commit-config.yaml .github/` returns hits in
       **both** files, inverting 001 T001 criterion 9.
    2. `! grep -A3 'SKIP:' .github/workflows/pr-checks.yml | grep -q scan-waitforresponse-race`
       succeeds. Written as a negated `grep -q`, **not** `grep -c ... = 0` (AR#3 G-19): `grep -c`
       exits **1** when the count is zero, so the success case reports as a failure under `set -e`
       or a naive `&&` chain. Same shape as the trap AR#2 caught in N-08.
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
    1. Branch `tmp/gate-red-team` **cut from `002-waitforresponse-lint-guard`**, not from `main`
       (AR#3 G-12). GitHub builds `pull_request` runs from the merge commit, so the guard step is
       present in the `Lint` job only if the branch descends from the feature branch. Cut from
       `main` and the check goes green against a workflow that does not contain the thing under
       test. Confirm with
       `git merge-base --is-ancestor 002-waitforresponse-lint-guard tmp/gate-red-team`.
    2. **Creating the commit requires the one bypass this design accepts** (AR#3 G-02). By this
       point T004's hook is installed and T009 has *proved* that committing this exact file is
       refused with no commit object created. `--no-verify` and `commit -n` are forbidden by
       CLAUDE.md policy and denied by the global `block-no-verify` hook. Use:
       `SKIP=scan-waitforresponse-race git commit -S -m "DO NOT MERGE [gate red-team] planted violation"`.
       This is deliberate and recorded. It is the bypass the spec already names as the local gate's
       known weakness (spec Edge Cases), and its necessity here is itself evidence the local hook
       fires. The point of mode (d) is that the required `Lint` job is **not** a pre-commit hook and
       is unaffected by `SKIP=`.
    3. The branch **also carries a deliberate ruff violation** under `src/` or `tests/`
       (AR#3 G-05). Without it the three ruff steps pass, the guard step runs regardless, and
       criterion 6 cannot fail — `if: always()` would be verified in the one environment where its
       absence makes no difference. FR-004's entire justification for the flag is that a failing
       ruff step would otherwise skip the guard, so that is the condition mode (d) must create.
    4. PR opened as **draft**, titled `DO NOT MERGE [gate red-team]`. Follows 1400 T006's precedent.
    5. `gh pr checks` shows the **`Lint`** check as **failed**.
    6. The `Lint` job log shows **both** the ruff failure **and** the guard step's failure in the
       same run, and the guard's output names the planted `file:line`. This is the assertion that
       distinguishes `if: always()` from its absence: a skipped guard step leaves only the ruff
       failure in the log.
    7. **Cleanup**: PR closed, remote branch deleted, local branch deleted. Verified with
       `gh pr list --state open` and `git branch -a`.
    8. After cleanup, the planted violation exists in **no commit on `main`**, and on no surviving
       branch or open PR. It necessarily existed on `tmp/gate-red-team` while the mode ran — that is
       what mode (d) tests. See SC-015, reworded to match (AR#3 G-11).

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
                       └───────────────────┴─► T008   (Phase D begins)
                                                 │
                                                 ▼
              T009 ─► T010 ─► T011 ─► T012 ─► T013 ─► T014 ─► T015 ─► T016 ─► T017
                                                 ▲
                        T013 deletes the planted fixture that T011 and T012 both
                        require, so Phase D is a STRICT CHAIN, not a fan-out.
                                                 │
                                                 ▼
                                               T018   (Phase E, real CI)
                                                 │
                                                 ▼
                                        T019 ─► T020   (Phase F)
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

**Every FR maps to ≥1 task. Every SC maps to ≥1 deciding task.** No orphans in either direction.
The table above deliberately shows SC-001 and SC-015 decided by more than one criterion (AR#3 G-18);
the earlier "exactly one" wording contradicted the table printed directly above it.

---

## Execution Log

Implemented 2026-07-30 on branch `002-waitforresponse-lint-guard`, cut from `main` at `d6e64fc`.

| Task | Date | Result | Evidence |
|---|---|---|---|
| T001 | 2026-07-30 | PASS | 001 landed at `daba1a9`; tree clean; `find frontend/tests/e2e -name "*.ts" \| wc -l` = 48 |
| T002 | 2026-07-30 | PASS (8/8) | Full evidence table in `contracts/detector-cli.md` C7 |
| T003 | 2026-07-30 | PASS, empty log | C7 records the gate ran and nothing diverged; detector not edited |
| T004 | 2026-07-30 | PASS | `pre-commit run scan-waitforresponse-race --all-files` exit 0 on clean tree |
| T005 | 2026-07-30 | PASS | Both "blocking" claims corrected; SKIP rationale untouched (`git diff` shows one deleted line) |
| T006 | 2026-07-30 | PASS | YAML parses; guard is `jobs.lint.steps[-1]`, plain `run:`, `if: always()` |
| T007 | 2026-07-30 | PASS | `make check-waitforresponse-race` exit 0; on `validate` line at `Makefile:42` |
| T008 | 2026-07-30 | PASS | Plant → `RACY 1 / PROMISE-FIRST 16 / OTHER 1 / total 18 / files scanned 49`, exit 1 |
| T009 | 2026-07-30 | PASS (4/4) | `git commit -S` exit 1; HEAD unchanged at `36a77d7`; output names `__scratch-race.spec.ts:8 RACY` and carries the corrected example |
| T010 | 2026-07-30 | PASS (5/5) | Index empty; `pre-commit run --all-files` exit 1 with **`scan-waitforresponse-race` the only Failed hook**, named by id, naming the planted `file:line`; isolated form exit 1 |
| T011 | 2026-07-30 | PASS (4/4) | `python3 -I -S` exit 1; interpreter `3.13.0`, matching the `Lint` job's `PYTHON_VERSION: '3.13'`. AR#2 N-01 reconfirmed: plain and `env -u VIRTUAL_ENV` both resolve to `.venv/bin/python3` |
| T012 | 2026-07-30 | PASS (5/5) | Detector renamed → hook exit 1, `python3 scripts/...` exit 2; undecodable `.ts` → exit 1 with `cannot read ...: 'utf-8' codec can't decode byte 0xff`, not a silent skip |
| T013 | 2026-07-30 | PASS (5/5) | Post-revert: hook 0, make target 0, `-I -S` 0, `git status` and `git stash list` both empty. Advisory: `pre-commit run --all-files` exit **0**, no failures |
| T014 | 2026-07-30 | **PARTIAL — crit 3 blocked, see below** | crit 1 (attributable form) and crit 2 PASS; crit 1 as literally written and crit 3 are unreachable on this tree |
| T015 | 2026-07-30 | PASS | `0.06s` real, three consecutive runs, against 48 files. Budget 2s; margin ~33x |
| T016 | 2026-07-30 | PASS | File count **1**: `scripts/scan-waitforresponse-race.py` |
| T017 | 2026-07-30 | PASS (3/3) | Hits in both `.pre-commit-config.yaml` and `.github/workflows/pr-checks.yml`; guard absent from `SKIP:`; step has `run:` and `if: always()` |

### T014 blocker: `make validate` never reaches the guard on this tree

`make validate`'s prerequisites run in order: `fmt lint security sast check-banned-terms
check-test-target-headers check-waitforresponse-race`. **`check-banned-terms` fails with 15
pre-existing matches** in `specs/1157-auth-cache-headers/`, `specs/1268-cors-404-headers/` and
`docs/cleanup/diagram-drift.md`, so make stops at `Makefile:98` and the guard target never executes.
Measured: `grep -c 'Checking waitForResponse race ordering'` over a full `make validate` run with the
violation planted returns **0**.

Consequences, stated precisely rather than papered over:

- **T014 crit 1 as literally written is satisfied for the wrong reason.** `make validate` does exit
  non-zero with the violation planted, but it would exit non-zero with no violation too. This is the
  identical attribution defect T010 crit 3 was written to forbid, so it is not accepted as evidence
  here either.
- **T014 crit 3 (`make validate` exits 0 after removing the violation) cannot pass**, and not
  because of anything this feature did.
- **The guard target itself is proven** in the attributable form: with the violation planted,
  `make check-waitforresponse-race` fails at `Makefile:47` (detector exit 1, make exit 2); with it
  removed, exit 0. FR-014's substance holds. What fails is the ability to observe it *through*
  `make validate`.

Not fixed here. The 15 matches live in files outside FR-010's allowlist, so clearing them is a
separate change, and reordering the prerequisites would not help: make halts on the first failing
prerequisite whatever the order. Carded rather than absorbed — see the board card added by T019.

---

## Adversarial Review #3 (Stage 8)

Independent reviewer over `spec.md` + `plan.md` + `tasks.md` + `contracts/` together, briefed on
implementation readiness rather than correctness: can T001–T020 be executed in order without
stopping, where is rework most likely, and which acceptance criteria could pass while the guard is
inert. Every load-bearing finding below was re-verified against the repository by the orchestrator
before the resolution was written. **21 findings: 2 CRITICAL / 5 HIGH / 8 MEDIUM / 6 LOW.**

### Findings and resolutions

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| G-01 | CRITICAL | **T003 had no executable path and was near-certain to fire.** The four amendments filed against 001 T001 were not gaps but direct contradictions: 001 crit. 6 read `sys.exit(0)` "otherwise"; crit. 8 mandated venv invocation; crit. 5 specified output as sites plus four counts with no stream, no files-scanned, no remediation text. 001 Clarification C4 closed with *"the guard can wire it in **without modification**"* — the prerequisite feature explicitly promising the opposite of this one's contract. A 001 implementer following 001's own tasks.md produces a detector failing ≥3 T002 criteria, discovered at the **second task** of this feature, with no task, branch, or FR-010 allowlist entry authorising the repair. | **Folded the contract into 001 before implementation** (commit `3b86d9c`). 001 T001 crit. 5, 6, 8 rewritten; new crit. 12 and 13 added; C4 amended to record the change rather than silently promising the old contract. Both features were still paper, so this cost one edit instead of an out-of-scope repair PR against a merged feature. T003 gains an explicit repair route for the residual case. Ground-rules ledger rewritten from "amendments Phase A discovers" to "contract folded in; Phase A verifies it landed". |
| G-02 | CRITICAL | **T018 was not executable.** It requires a branch carrying the planted violation, but by then T004's hook is installed and T009 has *proved* that commit is refused with no commit object created. `--no-verify` and `commit -n` are forbidden by CLAUDE.md and denied by the global `block-no-verify` hook. The only route is the `SKIP=` bypass the spec itself names as the local gate's known weakness, and no artifact mentioned it. An engineer stops here and asks. | T018 crit. 2 now states the exact command and frames it as the one deliberate, recorded use of the accepted bypass — noting that needing it is itself evidence the local hook fires, and that the required `Lint` job is not a pre-commit hook and is unaffected. Mirrored in quickstart §2b. |
| G-03 | HIGH | **T010 could pass with the guard completely inert.** Crit. 3 was a bare *`pre-commit run --all-files` exits non-zero*. That config runs ~20 hooks; any one going red satisfies it. T010 is the sole decider for SC-003, which the spec calls "the assertion that distinguishes this guard from `check-false-pass-patterns`". It distinguished nothing. This feature's own thesis defect, reproduced inside its own verification. | Crit. 3 now requires pre-commit to report `scan-waitforresponse-race` as `Failed` **by name** and its output to name the planted `file:line`; new crit. 4 adds the isolated single-hook run as corroboration. |
| G-04 | HIGH | **An AR#2 resolution was applied to the wrong mechanism.** N-14 raised that `python3` is not 3.13 everywhere and recorded the fix as *"Resolved by N-01's `-I -S`"* — but `-I -S` is verification mode (c), a manual command. The hook entry is `python3 scripts/...`, resolved from the committing shell's `PATH`, and was never touched. Verified: with the venv off `PATH`, `python3` here is **3.12.3**. Third instance in this feature of a ledger resolution naming a real fix and applying it elsewhere. | New **001 T001 crit. 13**: in-script `sys.version_info >= (3, 13)` floor exiting non-zero with the required version. N-14 left struck through in the AR#2 ledger rather than rewritten, because misapplied resolutions are what that ledger exists to catch. |
| G-05 | HIGH | **`if: always()` was asserted but never exercised.** T018's red-team PR carried only a `.ts` violation, so the ruff steps pass and the guard step runs with or without the flag. The property was verified in the one environment where it cannot fail — and FR-004's whole justification for the flag is a *failing* preceding step. | T018 crit. 3 adds a deliberate ruff violation under `src/` or `tests/`; crit. 6 requires the `Lint` log to show **both** failures in one run. Mirrored in quickstart §2b. |
| G-06 | HIGH | **A sixth requirement on 001's deliverable was un-filed.** Contract C6 row 6 ("ignores any file list; still scans its own root") had no backing 001 T001 criterion and was absent from the amendment ledger, which claimed five items and that "Phase A confirms each; it does not discover them". The property is load-bearing: `pass_filenames: false` plus an **untracked** planted file means only a filesystem-walking detector makes SC-003 work at all. Same class as AR#2's N-02, fixed for two of three cases. | Filed as **001 T001 crit. 12**, worded to forbid a narrowing positional `paths` argument. Ledger corrected to seven items. |
| G-07 | HIGH | **Phase A structurally could not verify the contract it gates.** T002 crit. 7 deferred remediation-guidance verification to T009 — in Phase D, after the hook, workflow step and make target have all landed. So one contract requirement was *guaranteed* to be discovered after the gate that exists to prevent wiring-before-verification, and T009 said to record it "per T003", a Phase A task already closed. Plan Phase A asserted the opposite invariant. | Moved into T002 as crit. 7: plant a throwaway violation, run the detector **standalone**, capture output, revert. Nothing is wired at T002. New crit. 8 states that Phase A is now a complete contract gate. Plan phase table corrected to match. |
| G-08 | MEDIUM | **FR-013's test covered the wrong failure mode.** FR-013 requires non-zero when the scan examines zero files; T002 crit. 5, SC-011 and quickstart tested only a *renamed* root. A detector that raises on a missing root but exits 0 on an existing-but-empty one satisfies every criterion while violating the requirement. | T002 crit. 5 now tests both shapes. 001 T001 crit. 6 worded as "files-scanned == 0 ⇒ non-zero, whether missing, renamed, or empty" rather than "root missing ⇒ non-zero". |
| G-09 | MEDIUM | plan.md and tasks.md disagreed on phase membership: FR-015's corrections were Phase C in the plan and Phase B (T005) in tasks; the scan-root rename was Phase D in the plan and Phase A in tasks. Stage 6 claims to have swept exactly this. | Plan phase table realigned to tasks.md, the executable artifact. |
| G-10 | MEDIUM | **T005's line citations go stale before T005 runs.** It targets `.pre-commit-config.yaml:190-192`, but T004 precedes it in the dependency graph and inserts ~10 lines of hook YAML into the same file, shifting the block to ~`:200`. | T005 crit. 1 and FR-015 now locate the block by its unique string *"as a BLOCKING gate"*, following 001's own PRE-SWEEP-locator discipline. |
| G-11 | MEDIUM | **SC-015 contradicted T018.** SC-015 said the planted violation "appears in no commit on any branch"; mode (d) *requires* committing it on `tmp/gate-red-team`. FR-007's wording was correct, T020 crit. 4 had a third variant. | SC-015 reworded to FR-007's form: no commit on `main`, no surviving branch or open PR after Phase E. T018 crit. 8 matched. |
| G-12 | MEDIUM | **T018 never stated the branch point.** `pull_request` runs build from the merge commit, so branching `tmp/gate-red-team` from `main` yields a `Lint` job with no guard step, a green check, and a recorded result about a workflow that does not contain the thing under test. | T018 crit. 1 requires the cut from `002-waitforresponse-lint-guard` and a `git merge-base --is-ancestor` confirmation. Mirrored in quickstart. |
| G-13 | MEDIUM | **The dependency graph contradicted T013 and would destroy T011/T012's fixture.** The graph drew T013 as a sibling of T011/T012; T013 crit. 1 deletes `__scratch-race.spec.ts`, which both require. The header said "depends on T009–T012". | Graph redrawn as a strict Phase D chain with the reason stated inline. |
| G-14 | MEDIUM | **FR-008's exception clause was unverified.** FR-008 forbids the detector swallowing a *scanning* exception and exiting 0; T012 covered only "detector absent". The named swallow was asserted by construction — the remaining half of AR#2's own N-10. | New T012 crit. 4: undecodable bytes in a `.ts` file under the scan root must produce non-zero, not a silent skip. |
| G-15 | MEDIUM | **Two green-state criteria depended on tooling this feature does not control.** T013 crit. 2 (`pre-commit run --all-files` exits 0) rides on trivy's daily-updating vulnerability DB — which `pr-checks.yml:187-189` documents can go red with no repo diff — plus checkov and detect-secrets. T013 crit. 4 / T014 crit. 3 (`make validate` exits 0, tree clean) run `fmt`, which is **mutating**, plus semgrep and pip-audit. "Tree clean after `make validate`" is not a property of this feature. | Pass/fail narrowed to the single-hook run and `make check-waitforresponse-race`. The full-config and full-validate runs are retained as **advisory**, explicitly not criteria. |
| G-16 | LOW | "6 of which contain matches" is a pre-001 figure presented as post-001. 001 T004 adds `helpers/search-helpers.ts`, which contains a `page.waitForResponse`, so the post-sweep figure is ≥7. The paired 47→48 file count was carefully corrected at AR#2 D-08; this one was not. | Labelled pre-001 and the derivation gap stated, matching how 47 is labelled. |
| G-17 | LOW | Requirement ordering is non-monotonic: FR-015 sits between FR-011 and FR-012, so a reader scanning for the last requirement stops there and misses FR-012 (the detector interface contract), FR-013 and FR-014. | Annotated in place with a forward pointer. Left in position because the block belongs with the FR-010/FR-011 scope material it was appended to. |
| G-18 | LOW | tasks.md asserted "Every SC maps to exactly one deciding task" directly below a table where SC-001 maps to two and SC-015 to three. | Reworded to "≥1 deciding task" with the contradiction noted. |
| G-19 | LOW | T017 crit. 2 used `grep -c ... ` expecting `0`, but `grep -c` **exits 1** when the count is zero, so the success case reports as failure under `set -e`. Same shape as the trap AR#2 caught in N-08. | Rewritten as a negated `grep -q`. |
| G-20 | LOW | quickstart used `git add -f` on the planted file, which is not gitignored (`git check-ignore` exits 1). An unexplained force flag in the one procedure that deliberately commits a violation invites a reader to assume an override is expected. | Dropped. |
| G-21 | LOW | FR-011(g) quoted the `Lint` job as running `ruff format --check src/ tests/`; the actual step is `ruff format --check --diff src/ tests/`. The load-bearing claim — that `scripts/` is outside every required check — is TRUE. | Quoted exactly. |

### Reviewer's factual audit

The reviewer independently re-checked roughly thirty specific assertions across these artifacts:
branch-protection contexts, job and step names, workflow line numbers, hook stages, pre-commit pin
skew, file counts, the 001 SC-001 arithmetic, the `next lint` directory constants, and every
`CLEANUP-BOARD.html` count. **Two were wrong**, both cosmetic and both fixed above (G-16, G-21).
Two claims the artifacts made *about the environment* were falsified and mattered: `python3` off the
venv is 3.12.3, not 3.13 (G-04), and the planted file is not gitignored (G-20).

It also confirmed empirically, in a scratch repository, the two mechanisms this design rests on:
that `stages: [pre-commit]` fires correctly under `default_stages: [commit]` on pre-commit 4.5.1 for
both `git commit` and `run --all-files`, and that an untracked planted file survives
`pre-commit run --all-files` and is seen by a filesystem-walking detector — the mechanism SC-003
depends on.

### Highest-risk task

**T003**, and the reviewer rated it higher than plan risk R1 did, having read 001's actual criteria
rather than this feature's summary of them. That risk is now **retired**: the contract is folded into
001 at `3b86d9c`, so T002 is expected to pass and T003 to record an empty log. Phase A remains a real
gate — a T002 failure now means the delivered script diverges from 001's own written criteria, which
is a different and much cheaper problem, and T003 crit. 2 carries the repair route.

The highest remaining risk is **T018**. It is the only task that depends on GitHub's behaviour rather
than the local tree, it now carries three separate preconditions that were each individually capable
of silently invalidating it (branch point, the bypass, the co-planted ruff violation), and it is the
only task whose failure mode is a *green* check.

### Most likely source of rework

The boundary between what Phase A can observe and what only Phases D and E can. Three properties the
contract treated as gated at Phase A were unobservable there: remediation guidance (G-07), `if:
always()` behaviour (G-05), and the hook's interpreter resolution (G-04). Each, on failure, sent work
backwards past a gate the plan describes as one-way. Compounding it, the two criteria most likely to
be run first — T010's bare "exits non-zero" and T013's bare "exits 0" — were both satisfiable by
unrelated hooks, so a run could look conclusive in either direction while saying nothing about the
guard. All three are now observable in the phase that claims to gate them, and both bare exit-code
criteria are attributed.

### Gate

**READY FOR IMPLEMENTATION.**

The reviewer returned **BLOCKED** on four findings (G-01, G-02, G-03, G-04) plus three strongly
recommended (G-05, G-06, G-07). All seven are resolved above, along with the remaining fourteen. The
four blocking ones were each re-verified against primary sources before being accepted — 001's T001
criteria and C4 read directly, T009/T010/T018's criteria read directly, and plan.md's N-14 row read
directly — rather than taken from the review's summary.

One resolution reached outside this feature: G-01 required editing `specs/001-waitforresponse-race-sweep/`,
which is committed on its own branch. It was made there (`3b86d9c`) and 002 rebased onto it, because a
fix landing only on 002's branch would not be visible to a 001 implementation and would not have been
a fix at all. **This is a cross-feature change and is flagged for the owner at the Phase 2 pause.**

Phase 3 remains gated on owner approval. No implementation has been performed.
