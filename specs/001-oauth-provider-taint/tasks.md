# Tasks: Close CodeQL alert 144 (OAuth provider taint)

**Input**: Design documents from `/specs/001-oauth-provider-taint/`
**Prerequisites**: spec.md (FR-001..FR-013 including FR-006a, SC-001..SC-007, Decision Gate),
plan.md (Implementation Design, Verification Design, Adversarial Review #2), research.md
(Decisions 1-5, Ledgers A and B), quickstart.md (Steps 0 through 5).
**Inherited convention**: `specs/001-ingestion-arn-logging/codeql-logging-convention.md`, consumed in
full per FR-008. Cited by document and section, never by a sibling requirement number and never by a
sibling line number.

**Organization**: tasks follow quickstart.md's step order. The code change is one atomic GPG-signed
commit; the phases after it are observation and classification, not further edits. Story labels map
to spec.md: US1 = apply the proven remediation, US2 = justified dismissal fallback, US3 = stop the
failed approach being retried.

**Tests**: FR-011 and SC-004 freeze the existing assertions. One new regression method is added under
constitution §3 (Testing, New code), and it is written and proven failing *before* the production edit (T007, T008), which
is the only way to show it is not vacuous.

---

## Execution invariants

These bind every task below. A task that breaks one of them has failed even if its own pass condition
was met.

1. **Never key anything on an alert number changing state.** The criterion is always
   **path + rule id**. `8424cbd` closed alert 117 at `oauth_state.py:95` and opened alert 144 at
   `oauth_state.py:104` at the identical timestamp (research.md Ledger B). Alert numbers appear below
   only as locating labels and as corroboration, never as a pass condition. The alerts API exposes no
   function field (`most_recent_instance.location` carries `path` plus line and column bounds only),
   so nothing keys finer than path + rule either.
2. **Empty output is only a pass when the read succeeded.** Every task reading from `gh`, a pipe, or a
   log captures the exit code explicitly and asserts a non-empty channel where emptiness would
   otherwise be indistinguishable from success. Pipelines are avoided entirely, or `PIPESTATUS[0]` is
   read. A failed read is discarded, never classified.
3. **`make validate` is NOT a gate for this feature.** `Makefile:42` chains `check-banned-terms`, and
   `scripts/check-banned-terms.sh` exits 1 on **17 pre-existing matches** in other features' spec
   directories (re-verified 2026-07-30: 15 of one legacy framework name, 2 of another; the names are
   not written here because writing them into this directory is what that scanner exists to prevent).
   `make sast` is the substitute, per quickstart Step 1c.
4. **No identifier is allocated at all.** Superseded 2026-07-31: the tech-debt registry was
   deleted and debt is now a `CLEANUP-BOARD.html` kanban card, which has no id field. The
   merge-time allocation-collision hazard this invariant guarded against no longer exists.
5. **Repo-wide alert counts are never a criterion.** SC-003 is an attribution test. Sibling
   `001-codeql-coverage` is expected to raise the repo-wide open count on purpose, and per the owner's
   directive that is success, not regression.
6. **Permission is established by reading scopes, never by attempting a mutation** (convention §5b).
   T006 is that read-only probe and it runs before anything in Phase 7 can execute.
7. **Every code-scanning alerts query MUST be paginated, and truncation MUST be proved absent.**
   An unpaginated query silently truncates and the truncation renders as **clean**. Measured on this
   repository 2026-07-30: `gh api repos/OWNER/REPO/code-scanning/alerts` filtered to `state == "open"`
   returns **zero** open alerts and exits **0**, because the default page size is 30 and the corpus is
   **137** with the open alerts sitting at numbers 144 to 150, past the end of page one.
   `per_page=100` is **not** a fix: page one at that size spans alert numbers 180 down to 59, which
   silently drops alerts 1 and 22 to 27, and 22 to 27 are precisely the `secrets.py` sanitize-in-place
   sites this feature reasons about. The mandatory shape is below, and it is used verbatim by T004,
   T020, T021 and T030.

   ```bash
   export ALERTS_JSON=/tmp/oauth-alerts.json
   gh api --paginate --slurp \
     "repos/$REPO/code-scanning/alerts?ref=refs/heads/main&per_page=100" > "$ALERTS_JSON"
   GH_RC=$?
   CORPUS=$(jq '[.[][]] | length' "$ALERTS_JSON"); JQ_RC=$?
   printf 'gh exit=%s jq exit=%s corpus=%s\n' "$GH_RC" "$JQ_RC" "$CORPUS"
   ```

   **Corpus floor**: `GH_RC=0`, `JQ_RC=0`, and `CORPUS` at least **137** (measured 2026-07-30). The
   floor is safe to assert as a minimum because code scanning alerts are never deleted; a fixed or
   dismissed alert stays in the all-states corpus forever, so this number only rises. A corpus below
   the floor is a truncated or failed read and **every** result derived from it is discarded, not
   classified.
   Two mechanical notes, both verified by running them: `--slurp` is rejected in combination with
   `--jq` ("the `--slurp` option is not supported with `--jq` or `--template`"), which is why the
   response is written to a file and filtered by standalone `jq` with its own exit code; and
   `--paginate` **without** `--slurp` applies `--jq` once per page, so a per-page `[...]` collector
   emits one array per page and the pass condition "output is exactly `[]`" would be met by a
   two-page response printing `[]` twice. Filtering the slurped file avoids both traps and involves
   no pipe, so no exit code is lost downstream of one.

---

## Terminal states

The feature MUST end in exactly one recorded state. There are no implicit aborts.

| State | Trigger | Recorded by |
|---|---|---|
| `CONFIRMED` | Fresh default-branch analysis shows zero open findings of this rule at this path | T024 |
| `REPORTED-FOREIGN-SINK` | A survivor of this rule on the path attributes outside `store_oauth_state()` | T025 |
| `REFUTED-DISMISSED` | A survivor attributes inside `store_oauth_state()` and is dismissed with the §2 justification | T026, T027 |
| `BLOCKED-ON-OWNER` | A survivor is observed and the T006 probe shows the dismissal permission absent | T028 |
| `BLOCKED-NO-ANALYSIS` | No analysis satisfying the T019 freshness proof within 7 days of the change landing on `main` | T029 |
| `BLOCKED-REGRESSION` | Unit suite not green, or a new open alert of any rule attributable to this diff on `oauth_state.py` or `secrets.py` | T029 |
| `PENDING-BRANCH-ANALYSIS` | Code change complete and green, but it has not landed on `main`, so no qualifying analysis can exist yet | T017 |

`PENDING-BRANCH-ANALYSIS` is inherited from `codeql-logging-convention.md` **§5a**, which calls it
"the normal ending, not an edge case", and is consumed here under FR-008 rather than newly defined.
It is absent from plan.md's six-row terminal-state table and from quickstart.md, which is recorded as
finding **F-01** in the Cross-Artifact Analysis below. Without it, an implementing agent that cannot
merge has no state to end in, which is precisely the implicit abort the gate exists to prevent.

### Routing for failures that are not gate outcomes

Added by Adversarial Review #3, finding **G-04**. Seven states cover every *gate* outcome, but six
task-level failure paths told the implementer to "stop" without naming a state, which is the same
implicit abort in a different place. **No new state is introduced.** Each is routed to an existing
one, and the routing is exhaustive: any task-level failure not listed here is `BLOCKED-REGRESSION`.

| Failure | State | Note |
|---|---|---|
| T001 wrong Python major/minor | `BLOCKED-REGRESSION` | The tree cannot be validated, so no gate may be evaluated on it. Report the interpreter version. No edit is made. |
| T002 dirty `src/` or `tests/` | `BLOCKED-REGRESSION` | **The likeliest of these.** Three sibling agents share this worktree and at least one of them edits `src/`. Report the foreign paths verbatim; do not revert them, and do not proceed, because T011, T015 and T016 all read a diff that would then be another feature's. |
| T004 complete read (corpus at or above floor) contains no entry for `$FILE` | `CONFIRMED` | The premise is gone before the work starts, and the definition of `CONFIRMED` is satisfied verbatim: no open finding of this rule at this path on the default branch. Record it as `CONFIRMED` **with the classification dated before the edit**, note that no change was needed, and still run T031 and T032 if the FR-013 comment is absent from the file. Do not "fix" a finding that is not there. |
| T016 `make sast` non-zero | `BLOCKED-REGRESSION` | Includes the offline case: `make sast` runs `semgrep scan --config auto`, which fetches registry rules over the network. A network failure is a blocked gate, not a clean one. |
| T023 read repeatedly not an observation | `BLOCKED-NO-ANALYSIS` | The discard-and-re-run row has no bound of its own. It inherits T019's: **7 days from `$CHANGE_SHA` landing on `main`**. A persistently failing `gh` read (token expiry, rate limit, outage) otherwise loops forever with no exit. |
| T026 `PATCH` fails for any reason other than permissions | `BLOCKED-ON-OWNER` | T028 is scoped to the permission case only. A 422, a 5xx or a network failure is still "the code change is complete and only the dismissal is outstanding", which is what T028 records. State the actual HTTP status in the handoff. |

One further routing correction: **T023's mixed-survivor precedence also triggers T027.** T026 running
in the mixed case is a real dismissal, and FR-007 and SC-006 require a registry entry for *any*
dismissal regardless of which state is finally recorded. The recorded state stays
`REPORTED-FOREIGN-SINK`; the registry entry is still mandatory.

---

## Phase 1: Preconditions and baseline (blocking, no edits)

- [ ] **T001** Environment precondition. Run `source .venv/bin/activate && python --version`.
  **Pass**: prints `Python 3.13.x`. Any other major/minor stops the feature before an edit is made.
- [ ] **T002** [P] Working-tree precondition. Run
  `git status --short -- src tests | tee /tmp/oauth-pre.txt; wc -l < /tmp/oauth-pre.txt`.
  **Pass**: prints `0`. A dirty `src/` or `tests/` means another agent is mid-edit in this shared
  worktree and the FR-003 diff inspection at T015 would be unreadable.
- [ ] **T003** [P] Unit baseline. Run `pytest tests/unit/auth/ -q; echo "pytest exit=$?"`.
  **Pass**: `pytest exit=0` **and** the summary line reads `30 passed` (re-verified 2026-07-30). Any
  other count means the baseline drifted and quickstart Step 1c's "expect 31 passed" is no longer the
  right target; record the new baseline and add one.
- [ ] **T004** [P] SC-003 baseline set, by path, never by count. Uses the paginated shape from
  invariant 7:
  ```bash
  export REPO=traylorre/sentiment-analyzer-gsk
  export RULE=py/clear-text-logging-sensitive-data
  export FILE=src/lambdas/shared/auth/oauth_state.py
  export ALERTS_JSON=/tmp/oauth-alerts-baseline.json
  gh api --paginate --slurp \
    "repos/$REPO/code-scanning/alerts?ref=refs/heads/main&per_page=100" > "$ALERTS_JSON"
  GH_RC=$?
  CORPUS=$(jq '[.[][]] | length' "$ALERTS_JSON"); JQ_RC=$?
  BASE=$(jq -c '[.[][] | select(.state == "open")
                       | {number, rule: .rule.id,
                          path: .most_recent_instance.location.path,
                          line: .most_recent_instance.location.start_line}]' "$ALERTS_JSON")
  printf 'gh exit=%s jq exit=%s corpus=%s\nbaseline=%s\n' "$GH_RC" "$JQ_RC" "$CORPUS" "$BASE"
  ```
  **Pass**: `gh exit=0`, `jq exit=0`, `corpus` at least **137**, **and** `$BASE` contains an entry
  whose `path` is `$FILE` and whose `rule` is `$RULE`. A corpus under the floor is a truncated read
  and the baseline is discarded, not recorded: an unpaginated version of this exact query returns an
  empty open set with exit 0 (invariant 7). A complete read that contains **no** entry for `$FILE`
  means this feature's premise is already gone: stop, record it, do not "fix" a finding that is not
  there.
  **Record**: the full set verbatim into `specs/001-oauth-provider-taint/evidence.md`. Observed
  2026-07-30: `{144, 147, 148, 149, 150}`, with 144 at `oauth_state.py:104`. Siblings legitimately
  move this set (`001-ingestion-arn-logging` closes 148-150, `001-bad-tag-filter-dead-suppression`
  closes 147, `001-codeql-coverage` raises it). Record the set, do not gate on its size.
- [ ] **T005** [P] Locating snapshot of alert 144, explicitly not a criterion. Run:
  ```bash
  A144=$(gh api "repos/$REPO/code-scanning/alerts/144" \
    --jq '{number, state, fixed_at, dismissed_reason,
           path: .most_recent_instance.location.path,
           start_line: .most_recent_instance.location.start_line,
           commit_sha: .most_recent_instance.commit_sha,
           code_flows: (.most_recent_instance.code_flows | length)}')
  RC=$?; printf 'gh exit=%s\n%s\n' "$RC" "$A144"
  ```
  **Pass**: `gh exit=0` and `$A144` non-empty. `code_flows` is expected to be `0`, which is why no
  artifact claims to know the taint path. Nothing downstream keys on this alert's state.
- [ ] **T006** [P] Read-only dismissal-permission probe (convention **§5b**; never probe by attempting
  a `PATCH`, which mutates alert state and cannot be cleanly reverted). Run:
  ```bash
  gh auth status 2>&1 | grep -i 'Token scopes'
  PERM=$(gh api "repos/$REPO" --jq '{visibility, permissions}')
  RC=$?; printf 'gh exit=%s\nperm=%s\n' "$RC" "$PERM"
  ```
  **Pass**: `gh exit=0`, `$PERM` non-empty, and the probe resolves to one of two recorded outcomes:
  *available* when `visibility` is `public` and `permissions.push` is `true` and the scope list
  contains `repo` (which subsumes `public_repo`); *absent* otherwise. **A missing `security_events`
  scope is NOT by itself a blocker**: GitHub requires it only on private repositories, and §5b exists
  to stop exactly that misreading. Observed 2026-07-30: scopes `gist, read:org, repo, workflow`,
  `visibility: public`, `permissions.admin: true`, so the outcome is **available** and
  `BLOCKED-ON-OWNER` is not the expected ending.

**Checkpoint**: baseline recorded, premise confirmed present, dismissal permission known in advance of
needing it. No file has been edited.

---

## Phase 2: US1 regression guard, written first

**Goal**: prove the guard fails on unfixed code before the fix exists. A guard that would pass either
way is decoration, and `caplog.text` assertions are the known instance of that failure mode.

- [ ] **T007** [US1] In `tests/unit/auth/test_oauth_state.py`, add `import logging` to the imports
  (the module does not currently import it; `OAUTH_STATE_TTL_SECONDS` is already imported) and add one
  method to `TestStoreOAuthState` (class at line 37), exactly as quickstart Step 1b specifies:
  ```python
      def test_log_context_excludes_provider(self, mock_table, caplog):
          """Regression guard for py/clear-text-logging-sensitive-data (alert 144).

          No value derived from `provider` may reach the logger's extra context.
          `logging` promotes every extra key to a LogRecord attribute, so this
          asserts on the sink itself rather than on rendered output, which is bare
          in production and would pass either way.
          """
          with caplog.at_level(
              logging.INFO, logger="src.lambdas.shared.auth.oauth_state"
          ):
              store_oauth_state(
                  mock_table, "state-1", "google", "https://example.com/callback"
              )

          records = [r for r in caplog.records if r.getMessage() == "OAuth state stored"]
          assert len(records) == 1
          assert not hasattr(records[0], "provider")
          assert records[0].has_user_id is False
          assert records[0].ttl_seconds == OAUTH_STATE_TTL_SECONDS
  ```
  The assertion is on the `LogRecord` attribute, never on `caplog.text`: rendered output is bare in
  production (research.md Decision 2) and a text assertion would pass on unfixed code. No existing
  assertion is edited (FR-011, SC-004).
- [ ] **T008** [US1] Prove the guard is not vacuous, before the production edit exists. Run
  `pytest tests/unit/auth/test_oauth_state.py -q; echo "pytest exit=$?"`.
  **Pass**: `pytest exit=1` **and** exactly one failure, `test_log_context_excludes_provider`, failing
  on `assert not hasattr(records[0], "provider")`. If it passes here, the guard is not testing the
  sink and T007 must be rewritten before proceeding.

**Checkpoint**: a failing, non-vacuous guard exists. It is red on purpose.

---

## Phase 3: US1 production change

- [ ] **T009** [US1] In `src/lambdas/shared/auth/oauth_state.py`, inside `store_oauth_state()` **only**
  (`def` at line 59): delete the `safe_provider` assignment (lines 99-101) and delete the
  `"provider": safe_provider` entry from the `extra` dict (line 105). Substitute nothing: not a
  literal, not an allowlist-selected constant, not a boolean (FR-001, FR-002; the allowlist form was
  deleted for cause by Adversarial Review #1 and must not return). Anchor by content, not by line
  number. The assignment must be **deleted, not orphaned**: `[tool.ruff.lint] select` includes `F`, so
  a retained unused local fails `ruff check` with `F841` and blocks the required `Lint` context
  (`.github/workflows/pr-checks.yml:62`).
- [ ] **T010** [US1] [US3] In the same edit, add the FR-013 documentation comment immediately above the
  `logger.info(` call:
  ```python
      # py/clear-text-logging-sensitive-data: no value derived from `provider` may
      # appear in this extra context. Removing the derived value, rather than
      # sanitizing it in place, is the shape that closed this rule in ebcc2f4.
      # See specs/001-oauth-provider-taint/research.md before adding a key here.
  ```
  Mandatory on **every** branch of the decision gate including `CONFIRMED` (FR-013). It carries no
  `# nosec`, `# noqa`, `# lgtm` and no CodeQL pragma, which is what keeps it disjoint from the inline
  suppression FR-010 forbids. Obligation inherited from `codeql-logging-convention.md` **§1**, closing
  paragraph, via FR-008.
- [ ] **T011** [US1] Confirm `validate_oauth_state()` is untouched (FR-004). Its
  `safe_provider_validated` at line 253 and `extra={"provider": safe_provider_validated}` at line 258
  carry the identical sanitize-in-place shape that left alerts 22-25 with `fixed_at` null to this day,
  and this feature does **not** fix it. Run:
  ```bash
  git diff -U0 -- src/lambdas/shared/auth/oauth_state.py | grep -E '^@@' ; echo "grep exit=$?"
  ```
  **Pass**: `grep exit=0` (hunk headers were printed, so the diff was read) **and** every hunk header's
  start line is below 122 (`def get_oauth_state` at 122 is the next top-level definition after the
  sink). Any hunk at or beyond line 154 means `validate_oauth_state()` was edited: revert it.

**Checkpoint**: the sink carries no `provider`-derived value and does carry the FR-013 comment.

---

## Phase 4: Local gates

- [ ] **T012** Run the guard against the fixed code:
  `pytest tests/unit/auth/ -q; echo "pytest exit=$?"`.
  **Pass**: `pytest exit=0` and the summary reads `31 passed` (30 baseline from T003 plus the T007
  method). FR-011, SC-004: no pre-existing assertion changed.
- [ ] **T013** [P] Lint and format the two touched files:
  ```bash
  ruff format src/lambdas/shared/auth/oauth_state.py tests/unit/auth/test_oauth_state.py
  ruff check src/lambdas/shared/auth/oauth_state.py tests/unit/auth/test_oauth_state.py
  echo "ruff exit=$?"
  ```
  **Pass**: `ruff exit=0`. Specifically no `F841`, which is the signal that T009's deletion left the
  `safe_provider` assignment orphaned.
- [ ] **T014** [P] **SC-007 check** on the working tree, before the commit:
  ```bash
  grep -n -B6 'OAuth state stored' src/lambdas/shared/auth/oauth_state.py; echo "grep exit=$?"
  grep -nEi '#\s*(nosec|noqa|lgtm)|codeql\[|lgtm\[' src/lambdas/shared/auth/oauth_state.py
  echo "pragma grep exit=$?"
  ```
  **Pass**: the first `grep exit=0` and its output contains the literal
  `py/clear-text-logging-sensitive-data` in the comment block preceding the log call; the second grep
  exits **exactly 1** (no match). Exit 2 is a grep error, not a clean file, and must be re-run. This
  same check is re-run against the merged file at T024 or T026, because SC-007 is stated against the
  merged file.
  **The window is `-B6`, and the arithmetic is load-bearing** (Adversarial Review #3, finding
  **G-01**). `grep` matches the string literal `"OAuth state stored",`, which after the T010 edit sits
  on the line *below* `logger.info(`, which sits below the four comment lines. The rule id is on the
  **first** comment line, exactly **five** lines above the match. `-B4` therefore prints lines 100 to
  104 and the rule id is not in the output, so the pass condition could never be met on correct code.
  Measured against the T009+T010 result 2026-07-30: `-B4` yields `0` occurrences of the rule id,
  `-B5` yields `1`. `-B6` is `-B5` plus one line of slack against a one-line drift in the comment.
- [ ] **T015** [P] **FR-003 check** by diff inspection:
  ```bash
  git diff -- src/lambdas/shared/auth/oauth_state.py > /tmp/oauth-fr003.diff
  echo "diff bytes=$(wc -c < /tmp/oauth-fr003.diff)"
  grep -cE '^[-+]' /tmp/oauth-fr003.diff
  ```
  **Pass**: `diff bytes` greater than 0 (an empty diff means nothing was applied, not that nothing
  changed), and the changed lines are confined to the deleted assignment, the deleted dict entry, and
  the added comment. The `put_item` item dict (including the persisted `"provider": provider` at line
  87), the returned `OAuthState`, and the `code_verifier` generation appear in no `+`/`-` line.
- [ ] **T016** [P] **FR-010 check**, that nothing was suppressed rather than fixed:
  ```bash
  git diff --name-only; echo "---"
  git status --short -- .github/ .semgrep* pyproject.toml
  make sast; echo "make sast exit=$?"
  ```
  **Pass**: `git diff --name-only` lists exactly `src/lambdas/shared/auth/oauth_state.py` and
  `tests/unit/auth/test_oauth_state.py` (plus files under `specs/001-oauth-provider-taint/`); the
  second command prints nothing, proving no analysis configuration, query pack, severity or path
  exclusion was touched; and `make sast exit=0`.
  **Do NOT run `make validate` as a gate** (invariant 3). If it is run anyway, confirm the only
  failures are the 17 pre-existing banned-term matches and that none of them is in this feature's
  directory: `bash scripts/check-banned-terms.sh 2>&1 | grep -c '001-oauth-provider-taint'` prints
  `0`. Do not repair other features' directories; three sibling agents share this worktree.

**Checkpoint**: the change is complete, green, and provably confined. This is the last point at which
any file is edited outside `specs/001-oauth-provider-taint/`.

---

## Phase 5: Land the change, or stop in a recorded state

- [ ] **T017** Commit GPG-signed on the feature branch (`git commit -S`; never `--no-gpg-sign`, never
  `--no-verify`), push, open a PR, and record the **merge commit SHA on `main`**:
  `export CHANGE_SHA=<merge commit sha on main>`.
  **If pushing or merging is gated on the repository owner and the change cannot land**, stop here and
  record terminal state **`PENDING-BRANCH-ANALYSIS`** per `codeql-logging-convention.md` §5a: the code
  change and its regression guard are complete and green, no default-branch analysis can exist yet,
  and the feature is neither done nor failed. Write the T020 gate query, filled in, into
  `specs/001-oauth-provider-taint/evidence.md` so the check is mechanical the moment the change lands.
  **Phases 6 and 7 are then not executed. Phase 8 still is** (Adversarial Review #3, finding
  **G-03**): T031 reads only `research.md` and has no dependency on a merge at all; T032 and T033 are
  declared **unconditional across every terminal state**, and this is the state quickstart Step 1d
  calls "the likeliest ending", so skipping the whole of Phase 8 here would leave FR-012, FR-013,
  SC-005 and SC-007 unverified on the most probable execution path. T032's "merged file" clause reads
  against the committed file on the feature branch in this state, and evidence.md records that
  substitution explicitly.
  **Also record `$CHANGE_SHA`, or its absence, into `evidence.md` rather than leaving it in the
  shell.** T019's freshness proof needs it and the wait it bounds is up to 7 days, which outlives any
  shell. A lost `$CHANGE_SHA` makes T019 unrunnable and strands the feature between
  `PENDING-BRANCH-ANALYSIS` and `BLOCKED-NO-ANALYSIS` with no way back. This applies on the normal
  path too, not only here.
- [ ] **T018** Locate a default-branch analysis. The `codeql` job (name `Analyze`, category
  `/language:python`) lives in `.github/workflows/pr-checks.yml` and triggers on `push` to `main`.
  ```bash
  AN=$(gh api "repos/$REPO/code-scanning/analyses?ref=refs/heads/main&per_page=5" \
    --jq '[.[] | {id, commit_sha, created_at, analysis_key, category}]')
  RC=$?; printf 'gh exit=%s\n%s\n' "$RC" "$AN"
  export ANALYZED_SHA=<commit_sha of the newest python analysis>
  ```
  **Pass**: `gh exit=0` and `$AN` is a non-empty array whose first element has category
  `/language:python`. An empty array with exit 0 means no default-branch analysis exists at all,
  which is a wait condition, not a pass.
  **Why this one is not paginated, unlike every alerts query** (invariant 7): the analyses endpoint
  returns results newest first (verified 2026-07-30: five consecutive `/language:python` analyses with
  strictly descending `created_at`), this task wants exactly the newest, and page one therefore
  contains it by construction. More importantly the truncation hazard does not apply here, because
  emptiness is a **failure** condition for this task rather than a pass: a truncated or failed read
  cannot render as clean. Paginating this endpoint would instead walk the repository's entire analysis
  history for a value already on line one.
- [ ] **T019** **Freshness proof (mandatory, FR-005 prerequisite).** A result predating the change
  decides nothing.
  ```bash
  ST=$(gh api "repos/$REPO/compare/$CHANGE_SHA...$ANALYZED_SHA" --jq '.status')
  RC=$?; printf 'gh exit=%s status=%s\n' "$RC" "$ST"
  ```
  **Pass**: `gh exit=0` and `$ST` is exactly `ahead` or `identical`. `behind` or `diverged` means the
  analysis does not cover the change: discard the observation and wait. An empty `$ST` is a failed
  read, not a pass.
  **Bound**: if no analysis satisfies this within **7 days** of `$CHANGE_SHA` landing on `main`, stop
  and record **`BLOCKED-NO-ANALYSIS`** via T029. Do not classify. Do not dismiss.

---

## Phase 6: Evaluate the decision gate, exactly once

- [ ] **T020** **Positive control for the gate query, run first.** A check whose pass condition is
  empty output is worthless without proof that the query can return anything at all: a typo in
  `$RULE`, `$FILE` or the ref returns `[]` forever and reads as success.
  ```bash
  export ALERTS_JSON=/tmp/oauth-alerts-gate.json
  gh api --paginate --slurp \
    "repos/$REPO/code-scanning/alerts?ref=refs/heads/main&per_page=100" > "$ALERTS_JSON"
  GH_RC=$?
  CORPUS=$(jq '[.[][]] | length' "$ALERTS_JSON"); JQ_RC=$?
  RULETOT=$(jq --arg r "$RULE" '[.[][] | select(.rule.id == $r)] | length' "$ALERTS_JSON")
  CTRL=$(jq -c --arg r "$RULE" --arg f "$FILE" \
    '[.[][] | select(.rule.id == $r)
            | select(.most_recent_instance.location.path == $f)
            | {number, state}]' "$ALERTS_JSON")
  printf 'gh exit=%s jq exit=%s corpus=%s rule_total=%s\ncontrol=%s\n' \
    "$GH_RC" "$JQ_RC" "$CORPUS" "$RULETOT" "$CTRL"
  ```
  This reads the same slurped corpus T021 filters, without the `state == "open"` predicate, so it
  returns findings of this rule at this path in **every** state. Note `jq --arg` is used here, which
  is a real `jq` flag; `gh api` has no `--arg` flag, which is the defect Adversarial Review #2 X1
  removed from quickstart Step 3a.
  **Pass**, all four, each a number measured 2026-07-30 rather than a vague "non-empty":
  `gh exit=0` and `jq exit=0`; `corpus` at least **137**; `rule_total` at least **22**; and `$CTRL`
  containing **alert 117**, which is `state: fixed` on this path for this rule and therefore an
  immovable anchor, so the control stays satisfied after the change lands whatever the outcome.
  Measured value of `$CTRL`: `[{"number":144,"state":"open"},{"number":117,"state":"fixed"}]`.
  If any of the four fails, the query shape or the read is broken and **T021's result is not an
  observation**. Alert 117 appears here as a fixture for the control, never as a criterion for the
  gate.
- [ ] **T021** [US1] **Primary gate query**, path + rule id, default branch only:
  Filters the **same slurped corpus T020 just validated**, so the anti-truncation floor has already
  been proved on the exact bytes this classification rests on. Do not re-fetch between T020 and T021.
  ```bash
  GATE=$(jq -c --arg r "$RULE" --arg f "$FILE" \
    '[.[][] | select(.state == "open")
            | select(.rule.id == $r)
            | select(.most_recent_instance.location.path == $f)
            | {number, start_line: .most_recent_instance.location.start_line,
               commit_sha: .most_recent_instance.commit_sha}]' "$ALERTS_JSON")
  JQ_RC=$?; printf 'jq exit=%s\ngate=%s\n' "$JQ_RC" "$GATE"
  ```
  **Pass condition for `CONFIRMED`**: T020 passed on all four of its floors, **and** `jq exit=0`,
  **and** `$GATE` is exactly `[]`. Because the expression always collects into an array, a **blank**
  `$GATE` means the filter itself failed and is discarded, never classified. Emptiness here is a pass
  only because T020 proved, on the same file, that a finding of this rule at this path is visible to
  this query when one exists.
  Per FR-009 and SC-002 this is the only admissible evidence: a green `Analyze` check on a pull
  request is not, because CodeQL is not a required status check here and a PR run reports into the
  PR's own ref.
- [ ] **T022** Attribute **every** survivor, only if `$GATE` is non-empty. This step can never turn a
  non-empty result into a pass; it decides **who owns** the survivor (FR-006a). Map at the analyzed
  commit, never against the working tree and never against a line window frozen at authoring time. No
  pipeline, so no exit code is lost downstream of one:
  ```bash
  gh api "repos/$REPO/contents/$FILE?ref=$ANALYZED_SHA" --jq '.content' > /tmp/oauth.b64
  RC=$?; printf 'gh exit=%s bytes=%s\n' "$RC" "$(wc -c < /tmp/oauth.b64)"
  base64 -d < /tmp/oauth.b64 > /tmp/oauth_at_analyzed.py; echo "base64 exit=$?"
  grep -n '^def ' /tmp/oauth_at_analyzed.py; echo "grep exit=$?"
  ```
  **Pass**: `gh exit=0`, `bytes` greater than 0, `base64 exit=0`, `grep exit=0`, and the output
  contains a `def store_oauth_state(` line. `store_oauth_state()` spans from its `def` line to the
  line before the next top-level `def`. A survivor whose `start_line` falls inside that span is this
  feature's; one outside it is not. If any of those four checks fails, the attribution is unknown, and
  an unknown attribution is handled as **foreign** (T025), never as this feature's to dismiss.
- [ ] **T023** [US1] **Classify, once** (FR-005, SC-005). Record the classification, the evidence it
  rests on, the analysis `id`, `$ANALYZED_SHA` and the T019 `compare` status into
  `specs/001-oauth-provider-taint/evidence.md`.

  | Observation | Classification | Next |
  |---|---|---|
  | T021 `gh exit=0` and `$GATE == []`, with T020 control non-empty | **Confirmed** | T024 |
  | `$GATE` non-empty, every survivor attributes inside `store_oauth_state()` | **Refuted** | T026 |
  | `$GATE` non-empty, any survivor attributes outside `store_oauth_state()` or is unattributable | **Not Confirmed, not this feature's** | T025 |
  | T021 `gh exit` non-zero, or `$GATE` blank, or T020 control empty | **Not an observation** | Discard, re-run T020 and T021 |
  | T019 never satisfied within 7 days | **Not decidable** | T029, `BLOCKED-NO-ANALYSIS` |

  **Mixed result precedence, stated here because neither spec.md's Decision Gate nor quickstart Step
  3c covers it** (finding **F-05**): if survivors exist both inside and outside the function, both
  obligations run. The inside survivor is dismissed under T026, the outside one is reported under
  T025, and the feature's recorded terminal state is **`REPORTED-FOREIGN-SINK`**, because FR-006
  forbids `CONFIRMED` while any finding is open at the path and FR-006a makes the reported state
  terminal.
  A survivor bearing an alert number other than 144 is **Refuted with a respawn recorded**, not
  success. The disappearance of alert 144 on its own decides nothing.

---

## Phase 7: Terminal branches (exactly one is executed, except as noted in T023)

- [ ] **T024** **`CONFIRMED`.** Record into `specs/001-oauth-provider-taint/evidence.md`: the analysis
  `id` and `commit_sha`, the T019 `compare` status, and the T021 result. Then:
  ```bash
  gh api "repos/$REPO/code-scanning/alerts/144" --jq '{number, state, fixed_at, dismissed_reason}'
  echo "gh exit=$?"
  ```
  `fixed_at` is recorded as **corroboration only** (expected non-null and dated at or after
  `$CHANGE_SHA`). It is not the criterion; the pass was already decided by T021, and 144 is a locating
  label. Note that `state` alone is not proof of repair: dismissal is sticky, which is why alerts 26
  and 27 read `dismissed` while carrying `fixed_at`, and alerts 22-25 read `dismissed` with `fixed_at`
  still null eight months on (convention §3, Trap 1).
  Then re-run the **T014 SC-007 check against the merged file**, and run the **SC-003 attribution
  recount** below. No dismissal. No tech debt entry (a closed finding creates no debt, FR-007).
- [ ] **T025** **`REPORTED-FOREIGN-SINK`** (FR-006a). Report to the repository owner, in
  `specs/001-oauth-provider-taint/evidence.md` and in the PR thread: the alert number, its
  `start_line`, `$ANALYZED_SHA`, the attributed function, and the statement that this feature does not
  own it. **Do not dismiss it. Do not edit `validate_oauth_state()`** (FR-004): its sink at lines 253
  to 258 carries the same sanitize-in-place shape that has left alerts 22-25 unrepaired since
  2025-12-09, and fixing it is a different feature's job. The code change from Phase 3 is
  independently complete and stays. **Pass**: the report exists and names all five items.
- [ ] **T026** [US2] **`REFUTED-DISMISSED`**, reachable only after Phase 3 landed and T023 classified
  Refuted (FR-007; a dismissal before the proven remedy is exhausted is blocked by US2 acceptance
  scenario 2), and only if T006 resolved to *available*. If T006 resolved to *absent*, go to T028
  instead without attempting the `PATCH`.
  The justification carries the three elements of `codeql-logging-convention.md` **§2** (what the value
  actually is; which convention shape was applied; why CodeQL still reports the flow), cited by
  section rather than by any sibling requirement number, per FR-008. Use the text drafted in quickstart
  Step 4b, adjusted to what was actually observed.
  ```bash
  export ALERT=<observed alert number, whatever it is>
  gh api -X PATCH "repos/$REPO/code-scanning/alerts/$ALERT" \
    -f state=dismissed -f dismissed_reason='false positive' \
    -f dismissed_comment="$JUSTIFICATION"
  echo "patch exit=$?"
  VER=$(gh api "repos/$REPO/code-scanning/alerts/$ALERT" \
    --jq '{number, state, dismissed_reason, dismissed_comment, dismissed_at,
           dismissed_by: .dismissed_by.login}')
  RC=$?; printf 'gh exit=%s\n%s\n' "$RC" "$VER"
  ```
  **Pass**: `patch exit=0`, `gh exit=0`, `$VER` non-empty, `state` is `dismissed`, `dismissed_reason`
  is `false positive`, and `dismissed_comment` is non-empty and contains all three §2 elements. A
  `PATCH` failing on permissions is an observation that routes to T028, not a retry loop.
- [ ] **T027** [US2] Tech debt card, required on this branch only (FR-007, SC-006: a dismissal is a
  documented security shortcut). **Re-targeted 2026-07-31**: this task wrote a
  `docs/reference/TECH_DEBT_REGISTRY.md` entry; `001-constitution-prune` deleted both that file and
  the constitution section mandating it. Add a card to the `CARDS` array in **`CLEANUP-BOARD.html`**
  instead, with `lane: "track"`, `severity` set from the surviving alert, `title` naming
  `store_oauth_state()`, `evidence` carrying the alert number and the exact dismissal justification,
  `citation` `src/lambdas/shared/auth/oauth_state.py`, `next_action`, and `source` naming this
  directory. No identifier is allocated (invariant 4).
  **Pass**: the board's `CARDS` array still parses as JSON and contains a card whose evidence names
  the dismissed alert number.
- [ ] **T028** **`BLOCKED-ON-OWNER`**, reached only when the T006 read-only probe resolved to *absent*
  or a T026 `PATCH` failed on permissions. Inherited from `codeql-logging-convention.md` **§5b**, not
  newly defined. Write a handoff artifact into `specs/001-oauth-provider-taint/` carrying: the exact
  alert numbers observed at the path with their `start_line` and `$ANALYZED_SHA`; the exact
  justification text verbatim per alert; and the exact `gh api -X PATCH` invocation, ready to run.
  State plainly that the code change is independently complete and mergeable and only the dismissal is
  outstanding. Reported as neither done nor failed.
  **Pass**: the artifact exists and carries all three items.
- [ ] **T029** **`BLOCKED-NO-ANALYSIS`** or **`BLOCKED-REGRESSION`**. Report to the repository owner,
  naming the missing analysis (for the former) or the exact failing check (for the latter). Neither is
  classified against the gate and neither is dismissed; both are terminal and reportable, not a further
  attempt. `BLOCKED-REGRESSION` triggers on a non-green unit suite **or** on a new open alert of any
  rule appearing on `src/lambdas/shared/auth/oauth_state.py` or on `src/lambdas/shared/secrets.py`
  (SC-003). It does **not** trigger on the repo-wide count moving: `001-codeql-coverage` is expected to
  raise it and that is success, not regression.
- [ ] **T030** **SC-003 attribution recount**, run on whichever of T024, T025 or T026 was reached:
  ```bash
  export AFTER_JSON=/tmp/oauth-alerts-after.json
  gh api --paginate --slurp \
    "repos/$REPO/code-scanning/alerts?ref=refs/heads/main&per_page=100" > "$AFTER_JSON"
  GH_RC=$?
  CORPUS=$(jq '[.[][]] | length' "$AFTER_JSON"); JQ_RC=$?
  AFTER=$(jq -c '[.[][] | select(.state == "open")
                        | {number, rule: .rule.id,
                           path: .most_recent_instance.location.path}]' "$AFTER_JSON")
  AFTER_RC=$?
  # Positive control for the path selector itself. This is an ABSENCE assertion, and an absence
  # is not evidence until the read is proved working (Adversarial Review #3, finding G-02).
  PATHCTRL=$(jq '[.[][] | select(.most_recent_instance.location.path == null)] | length' "$AFTER_JSON")
  PATHCTRL_RC=$?
  ANCHOR=$(jq -c '[.[][] | select(.number == 117)
                         | {number, state, path: .most_recent_instance.location.path}]' "$AFTER_JSON")
  ANCHOR_RC=$?
  printf 'gh exit=%s jq exit=%s after_rc=%s corpus=%s null_paths=%s (rc=%s) anchor_rc=%s\nanchor=%s\nafter=%s\n' \
    "$GH_RC" "$JQ_RC" "$AFTER_RC" "$CORPUS" "$PATHCTRL" "$PATHCTRL_RC" "$ANCHOR_RC" "$ANCHOR" "$AFTER"
  ```
  **Pass**, and every clause is required:
  `gh exit=0`; `jq exit=0`, `after_rc=0`, `rc=0` and `anchor_rc=0`; `corpus` at least **137**
  (invariant 7: without `--paginate` this comparison silently reads zero open alerts and would certify
  SC-003 while blind); `null_paths` exactly **0**; `$ANCHOR` exactly
  `[{"number":117,"state":"fixed","path":"src/lambdas/shared/auth/oauth_state.py"}]`; **and** no alert
  of any rule newly appears on `src/lambdas/shared/auth/oauth_state.py` or on
  `src/lambdas/shared/secrets.py` relative to the T004 baseline.
  **Why the two extra controls exist.** T030 is the feature's only *other* pass-on-absence condition
  besides T021, and unlike T021 it had no control. The corpus floor proves the **fetch** worked; it
  proves nothing about the **path selector**. Demonstrated 2026-07-30 by running it: mistyping
  `.location` as `.locatio` does not make `jq` fail. It returns `path: null` for all 137 entries,
  exits **0**, leaves the corpus floor satisfied, and the resulting set contains no entry on
  `oauth_state.py` or `secrets.py`, so the pass condition is met while the read is blind. That is
  exactly the shape T020 exists to prevent on the gate query. `null_paths = 0` catches a broken
  selector; the alert-117 anchor catches a selector that is well-formed but reading the wrong field,
  because 117 is permanently `fixed` at this exact path and its path string is therefore an immovable
  fixture (same anchor as T020, same reason).
  A higher total attributable to `001-codeql-coverage`'s additional analysis leg satisfies
  SC-003; it does not breach it. Record the set difference against T004 and name the sibling feature
  that owns each movement. **The count is not the test.**

---

## Phase 8: US3 durability and close-out

- [ ] **T031** [P] [US3] Verify the prior-art record satisfies FR-012 without reading commit history.
  ```bash
  grep -c '8424cbd\|0e7a375\|ebcc2f4' specs/001-oauth-provider-taint/research.md
  echo "grep exit=$?"
  ```
  **Pass**: `grep exit=0` and the count is at least 3, **and** by inspection research.md states: that
  `8424cbd` *relocated* the finding rather than failing to clear it, naming alert 117 (line 95,
  `fixed_at` 2026-01-20T22:34:56Z) and alert 144 (line 104, `created_at` the same timestamp); that the
  rule `8424cbd` addressed was log injection, a different rule; that `0e7a375` failed via an
  intermediate variable and spawned alerts 110 and 111; and that `ebcc2f4` succeeded by removing the
  value from the log context. All four are present in research.md Ledgers A and B as written.
- [ ] **T032** [P] [US3] Verify US3's second acceptance scenario is discharged **in the code**, not only in
  `specs/`. Re-run the T014 check against the merged file: a reader with only
  `src/lambdas/shared/auth/oauth_state.py` in front of them is warned at the sink and pointed at
  `specs/001-oauth-provider-taint/research.md`. **Pass**: the rule id and the pointer are both present
  and no suppression pragma is. This is unconditional across every terminal state including
  `CONFIRMED` (FR-013, SC-007).
- [ ] **T033** Close-out. `specs/001-oauth-provider-taint/evidence.md` names exactly one terminal
  state, the observation it rests on, the analysis id and `commit_sha` where applicable, and the T030
  set difference. **Pass**: exactly one terminal state is named (SC-005); a document naming two, or
  none, is not a close-out.

---

## Dependencies and parallelism

```
T001 ──> T002,T003,T004,T005,T006  [P, all five independent reads]
     └─> T007 ──> T008 ──> T009 ──> T010 ──> T011
                                       └─> T012 ──> T013,T014,T015,T016  [P]
                                                       └─> T017 ──> T018 ──> T019
                                                                        └─> T020 ──> T021 ──> T022 ──> T023
                                                                                                  └─> one of T024 / T025 / T026+T027 / T028 / T029
                                                                                                          └─> T030 ──> T031,T032  [P] ──> T033
```

- **Parallelizable**: T002, T003, T004, T005, T006 (Phase 1 reads, no shared state); T013, T014, T015,
  T016 (all read-only over an already-applied diff); T031 and T032. **Eleven tasks marked [P].**
- **Hard ordering that must not be relaxed**: T007 before T009 (a guard proven failing first is the
  only proof it is not vacuous); T020 before T021 (a control before a check whose pass is emptiness);
  T019 before T021 (a stale analysis decides nothing); T006 before T026 (permission is read, never
  probed by mutation); T009-T012 before T026 (FR-007: the proven remedy is exhausted before any
  dismissal).

---

## Requirement coverage

Every functional requirement and every success criterion maps to at least one task. No gaps.

| Requirement | Tasks |
|---|---|
| FR-001 no `provider`-derived value in the `extra` context | T009, T007 (guard), T012 |
| FR-002 satisfied by removal, nothing substituted | T009, T015 |
| FR-003 runtime behavior outside the log call unchanged | T015, T012 |
| FR-004 `validate_oauth_state()` not modified | T011, T025 |
| FR-005 outcome classified against the decision gate | T023, T033 |
| FR-006 Confirmed requires zero open findings of this rule at this path | T020, T021, T023 |
| **FR-006a** survivor attributed before it is acted on; foreign survivor reported, not dismissed | **T022, T023 (precedence), T025** |
| FR-007 dismissal only after the change is applied and refuted; registry entry required | T026, T027 |
| FR-008 consume `codeql-logging-convention.md` in full, cite by section | T006 (§5b), T010 (§1), T017 (§5a), T024 (§3), T026 (§2), T028 (§5b) |
| FR-009 closure evidenced from default-branch state, never a PR check | T018, T019, T021 |
| FR-010 no suppression, severity change, exclusion or pragma | T016, T014 |
| FR-011 existing OAuth unit tests pass unmodified | T012, T007 |
| FR-012 prior-art record names what was tried and what worked | T031 |
| FR-013 unconditional site comment naming the rule id, no pragma | T010, T014, T032 |
| SC-001 zero open findings of this rule at this path | T021, T023 |
| SC-002 evidence from default-branch analysis or the alerts API | T018, T019, T021 |
| SC-003 no new alert attributable to this diff on `oauth_state.py` or `secrets.py` | T004 (baseline), T030 (recount), T029 (trigger) |
| SC-004 existing suites pass with no assertion changes | T003, T012 |
| SC-005 exactly one classification, on stated evidence | T023, T033 |
| SC-006 dismissal justification non-empty and per convention; registry entry exists | T026, T027 |
| SC-007 site comment present on the merged file, no pragma | T014, T024, T032 |

**Coverage: 14 of 14 functional requirements (FR-001 to FR-013 including FR-006a), 7 of 7 success
criteria. No requirement is unmapped, and no task exists without a requirement behind it.**

**Terminal-state coverage: 7 of 7** (`CONFIRMED` T024, `REPORTED-FOREIGN-SINK` T025,
`REFUTED-DISMISSED` T026 and T027, `BLOCKED-ON-OWNER` T028, `BLOCKED-NO-ANALYSIS` T029,
`BLOCKED-REGRESSION` T029, `PENDING-BRANCH-ANALYSIS` T017).

---

## Cross-Artifact Analysis

Scope: `spec.md`, `plan.md`, `research.md`, `quickstart.md`, `tasks.md`, plus the inherited
`specs/001-ingestion-arn-logging/codeql-logging-convention.md`. Adversarial Reviews #1 and #2 are not
re-litigated; findings below are either new, or are cases where a review's stated fix did not reach
every site. Every claim was re-derived by running the thing.

### Findings

| # | Severity | Finding | Evidence | Disposition |
|---|---|---|---|---|
| **F-01** | **HIGH** | **The inherited convention defines a terminal state this feature never adopted.** `codeql-logging-convention.md` §5a defines `PENDING-BRANCH-ANALYSIS` and calls it "the normal ending, not an edge case": closure is read from a default-branch analysis, and none can exist while the change sits on a branch. FR-008 requires consuming that document **in full**, yet plan.md's terminal-state table lists six states and omits it, and quickstart.md never mentions it. `BLOCKED-NO-ANALYSIS` is not the same state: it triggers 7 days **after** the change lands on `main`, so an implementing agent whose push is owner-gated has no state to end in and aborts implicitly. | plan.md:207-216 ("Exactly six"); convention §5a lines 132-142; quickstart.md greps clean for the string. | **FIXED in all four artifacts** on coordinator instruction. tasks.md T017 and the terminal-state table; spec.md FR-008 now names both §5 states explicitly and the Decision Gate carries a `PENDING-BRANCH-ANALYSIS` row plus a paragraph distinguishing it from the 7-day bound; plan.md's table gained the row and reads "Exactly seven"; quickstart.md gained Step 1d and lists all seven in its header. Adopted as inheritance under FR-008, never as a new definition. |
| **F-02** | **HIGH** | **spec.md's Edge Cases still key success on the *function*, contradicting FR-006 and SC-001.** The second edge case reads "Success is the function being free of open findings for this rule". Adversarial Review #2's X3 moved the criterion to **path + rule id** and rewrote FR-006, the gate's scoping paragraph, plan.md's verification design and quickstart 3b, but this sentence survived. On the exact evidence X3 cited (a survivor in the FR-004-frozen `validate_oauth_state()`), the Edge Case returns success while FR-006 and SC-001 return failure. That is the same contradiction X3 was raised to remove, at a site the sweep did not reach. AR#2's own note says the sweep was redone "across acceptance scenarios and independent tests"; Edge Cases was not in that list. | spec.md:198-200 versus spec.md:222-228 (FR-006) and spec.md:308-316 (SC-001). | **FIXED in spec.md** on coordinator instruction. The bullet is re-keyed to path plus rule id with the reason stated inline (a function-scoped reading derives from a `start_line` and reimports the line instability the gate exists to avoid), and two bullets were added covering the foreign-sink case and `PENDING-BRANCH-ANALYSIS`. **Edge Cases were then swept exhaustively for the same error: this was the only instance.** The remaining `store_oauth_state()` mentions in that section are attribution language under FR-006a, which is correct, not gate criteria. |
| **F-03** | **HIGH** | **Five sibling citations are already stale, three of them by exactly one line.** Campaign rule 5 said two had gone stale; it is now at least five. Re-derived 2026-07-30: spec.md Q1 cites sibling FR-010 as `spec.md:92`, but line 92 is now **FR-009**; Q3 cites the three-element wording as sibling "FR-009 (`spec.md:91`)", but line 91 is now **FR-008b**; Q3 cites sibling FR-011 as `spec.md:93`, but line 93 is now **FR-010**. The sibling inserted an FR-008b and shifted everything below it. Also stale: AR#2 X2 cites `specs/001-codeql-coverage/spec.md:427` as "its own SC-004", but line 427 is prose about tolerance widths; and spec.md Q2 cites `specs/001-codeql-coverage/plan.md:282` as settling merge-time TD allocation, but line 282 is about a §10 local-SAST gap. | `sed -n '90,96p' specs/001-ingestion-arn-logging/spec.md`; `sed -n '427p' specs/001-codeql-coverage/spec.md`; `sed -n '282p' specs/001-codeql-coverage/plan.md`. | **Not fixed here.** tasks.md cites the convention document by **section only** and cites no sibling line number anywhere. The stale citations are all in Clarifications and Adversarial Review appendices, so they are provenance rather than normative, but the rot is real and confirms the rule. |
| **F-04** | **MEDIUM** | **quickstart.md Step 3a's primary gate command sits inside a broken code fence.** Line 205 opens a bash code fence, lines 206-209 are English prose about the missing `--arg` flag, and line 211 opens a second bash fence. Per CommonMark a closing fence may not carry an info string, so line 211 closes nothing: the prose, the second fence marker and the command all render inside one bash block. AR#2's X1 fix repaired the command's content and left the fence malformed, so the single most load-bearing command in the runbook is not cleanly copy-pasteable. | quickstart.md:203-218 raw. | **FIXED in quickstart.md** on coordinator instruction. Step 3a is restructured into prose, a `#### The control, first` block and a `#### The gate itself` block, each in its own well-formed fence. The command is now copy-pasteable, and is also the paginated shape required by F-11. |
| **F-05** | **MEDIUM** | **No artifact classifies a mixed survivor set.** spec.md's Decision Gate and quickstart Step 3c each have one row for "attributed to `store_oauth_state()`" and one for "attributes outside", with no rule for both being present at once. FR-006a is written per-survivor ("A survivor MUST be attributed before it is acted on"), so both obligations apply, but nothing says which terminal state is recorded. | spec.md:289-295; quickstart.md:253-260. | **Resolved in tasks.md** T023 by a stated precedence derived from the existing requirements, not a new one: both obligations run, and the recorded state is `REPORTED-FOREIGN-SINK` because FR-006 forbids `CONFIRMED` while any finding is open at the path and FR-006a makes the reported state terminal. |
| **F-06** | **MEDIUM** | **quickstart.md contradicts campaign rule 6 and convention §5b on how permission is established.** Step 4c says `BLOCKED-ON-OWNER` is "Reached if Step 4b's `PATCH` fails on permissions", and no read-only probe appears anywhere in the runbook. §5b is explicit: "Check the permission with a read-only probe. **Never establish it by attempting a dismissal**, which mutates alert state and cannot be cleanly reverted." AR#2 section D dismissed this as "not the anti-pattern the sibling forbids" because Step 4b is the intended dismissal rather than a probe; that reasoning holds only if the probe happened earlier, and it never does. | quickstart.md:353-358; convention §5b lines 146-164. | **FIXED in quickstart.md and spec.md** on coordinator instruction, who has struck the earlier clearance. quickstart gained **Step 0b**, a read-only probe placed before the change is even applied and therefore before any step that could mutate an alert; Step 4b is now explicitly gated on its outcome and Step 4c is entered from the probe rather than from a failed `PATCH`; the anti-checklist gained a bullet. spec.md FR-008 now carries §5b's probe rule and the "`security_events` is a private-repository requirement" carve-out. tasks.md T006 already covered it. Probe run 2026-07-30: scopes `gist, read:org, repo, workflow`, `visibility: public`, `permissions.admin: true`, so dismissal is **available**. |
| **F-07** | **LOW** | **quickstart.md's header says five terminal states; there are six in plan.md and seven counting the inherited §5a state.** Stale since FR-006a and `REPORTED-FOREIGN-SINK` were added. | quickstart.md:5-6 versus plan.md:207. | **FIXED.** quickstart's header now says seven and enumerates them; plan.md says seven; tasks.md says seven. |
| **F-08** | **LOW** | **quickstart Step 0's inline comment reads "expect exactly 5 open alerts", four lines above a paragraph explaining that the count is not the test.** Harmless as prose, but it is exactly the shape SC-003 was rewritten to remove, sitting in the copy-pasteable part where an operator will read it as the pass condition. | quickstart.md:20 versus quickstart.md:41-46. | **FIXED.** The comment now reads "Record the SET, never the count", and the acceptance text asserts the corpus floor plus the presence of this path's entry. |
| **F-09** | **LOW** | **quickstart Step 5's anti-checklist still uses function scoping.** "Reporting `CONFIRMED` because alert 144 disappeared, without checking whether a replacement number appeared **inside the same function**." Post-X3 the criterion is the path. The bullet is right in spirit and stale in wording. | quickstart.md:393-394. | **FIXED.** Re-keyed to "a replacement number for this rule anywhere on the path", with the 117-to-144 evidence stated in the bullet. |
| **F-10** | **LOW** | **spec.md's status line still reads "Draft (revised after Adversarial Review #1)"** after Adversarial Review #2 landed in plan.md and rewrote FR-006, SC-003 and the gate. | spec.md:5. | **FIXED.** Now names both adversarial reviews and this cross-artifact analysis. |
| **F-11** | **HIGH** | **Every code-scanning alerts query in this feature was unpaginated, and truncation renders as CLEAN.** Raised by a sibling after Stage 7 and re-derived here against the live API. Measured 2026-07-30: `gh api repos/OWNER/REPO/code-scanning/alerts` filtered to open alerts returns **zero** and exits **0**, on a repository with five open; default page size is 30 against an all-states corpus of **137**, and the open alerts sit at 144 to 150, past the end of page one. `per_page=100` is not a fix: page one at that size spans numbers 180 down to 59 (`{"max":180,"min":59,"n":100}`), silently dropping alerts 1 and 22 to 27, and 22 to 27 are the `secrets.py` sanitize-in-place sites this feature's whole `fixed_at` argument rests on. Worst placement was tasks.md's T020 **positive control**, whose entire job is to prove the gate query can see anything: a truncated control certifies the gate while blind. | `gh api ".../alerts" --jq '[.[]\|select(.state=="open")]\|length'` returns 0, exit 0; `gh api --paginate --slurp` yields 2 pages, `[.[][]]\|length` = 137, open set `[150,149,148,147,144]`; alerts 22-27 present only via page 2. | **FIXED in tasks.md, quickstart.md and plan.md.** New invariant 7 in tasks.md fixes the mandatory shape: `--paginate --slurp` into a file, standalone `jq` with its own exit code, no pipe, and an asserted corpus floor. T004, T020, T021 and T030 rewritten; quickstart Step 0a, Step 3a and Step 4a rewritten; plan.md verification step 1 states why pagination is load-bearing rather than hygienic. The T020 control is kept, as instructed, and its floor is now three measured numbers (corpus 137, rule total 22, and the presence of alert 117, which is permanently `fixed` at this path) rather than "non-empty". Two mechanical constraints verified by running them: `--slurp` is rejected with `--jq`, and `--paginate` without `--slurp` applies `--jq` per page, so a two-page response would print `[]` twice and satisfy an "output is `[]`" condition twice over. The analyses endpoint is deliberately left unpaginated, with the reason stated at T018: it is newest-first, this feature wants exactly the newest, and emptiness is a **failure** condition there rather than a pass, so truncation cannot render as clean. |

**No finding of any severity was raised against**: requirement coverage (14/14 FRs, 7/7 SCs mapped,
no orphan tasks); the ordering graph (no task depends on a later one); the regression guard's
falsifiability (it asserts `not hasattr(record, "provider")` over the `LogRecord`, so it fails on
today's code, and no `caplog.text` assertion exists in any artifact); the banned-term surface (this
directory greps clean, re-verified); or the `TD-` identifier (no artifact of this feature names a
number, re-verified across all five files).

### Unfalsifiable pass conditions

Swept deliberately, because a check that cannot fail is the campaign's recurring defect.

- **T021 is the one task whose pass condition is emptiness.** It is made falsifiable by four things:
  the **corpus floor** of 137, without which an unpaginated read of an empty page reads as a clean
  repository (F-11); the T020 positive control, which proves the query can return results at this path
  for this rule and which stays satisfied permanently because alert 117 is `fixed` there; the explicit
  `gh` and `jq` exit assertions; and the distinction between the string `[]` (a real empty result) and
  a blank string (a failed filter), which the array collector makes observable. The floor and the
  control are independent: the floor catches a truncated or failed read, the control catches a
  well-formed read filtered by a typo'd path or rule.
- **T014's second grep passes on exit 1**, which is a match-absent result and not an error. Exit 2 is
  called out explicitly as a re-run condition, because a grep error would otherwise read as clean.
- **T016 asserts a non-empty diff before asserting what is in it**, so "nothing was applied" cannot
  masquerade as "nothing forbidden was applied".
- **T022 avoids pipelines entirely** rather than relying on `PIPESTATUS[0]`, and routes an
  unattributable survivor to the foreign branch rather than to the dismissal branch. quickstart Step 3b
  keeps the pipeline and mentions `PIPESTATUS[0]` only in prose after the command (AR#2 X9, recorded
  and left); tasks.md does not.
- **No task's pass condition is "CI is green"**, and none cites a pull request check as closure
  evidence (FR-009, SC-002).

### Quickstart versus tasks disagreements

Five were recorded at first authoring. Four have since been closed by repairing quickstart.md on
coordinator instruction, so they are kept here as a record of what was found rather than as live
disagreements.

1. **Permission probe** (F-06): **closed.** quickstart gained Step 0b, a read-only probe placed before
   any step that can mutate an alert, and Steps 4b and 4c now key on its outcome. Convention §5b
   governs and both documents now follow it.
2. **Test-first ordering**: **open, and deliberately.** quickstart Step 1 applies the source edit (1a)
   before adding the test (1b); tasks.md inverts this (T007, T008 before T009) so the guard is proven
   failing on unfixed code. Nothing in quickstart forbids it and the constitution §3 accompaniment gate
   is satisfied either way, so quickstart is left alone. The inverted order is what makes the guard's
   non-vacuity checkable rather than asserted, and tasks.md is the document the implementer executes.
3. **Terminal-state count** (F-01, F-07): **closed.** All three documents now say seven and name the
   same seven.
4. **Gate query hygiene** (F-04, F-11, T020): **closed.** quickstart Step 3a now carries the control,
   the corpus floor and the paginated shape, in well-formed fences.
5. **Baseline framing** (F-08): **closed.** quickstart Step 0a records the set and asserts the corpus
   floor; neither document states an expected count as a pass condition.

### Verdict

**PASS.** Revised after the repair pass: ten of the eleven findings are fixed in the artifacts, and
the one that is not (**F-03**, five stale sibling citations) is deliberately left alone at the
coordinator's instruction, because cross-feature citations are being swept campaign-wide in one pass
after the final stage and repairing them now guarantees they drift again. The evidence for all five
is recorded in the F-03 row.

The artifact set is internally consistent on everything load-bearing. The criterion is path plus rule
id in FR-006, FR-006a, SC-001, the Decision Gate, the Edge Cases, plan.md's verification design,
research.md Decision 4, quickstart Step 3a and every task here. No success criterion, acceptance
scenario, Independent Test, Edge Case or task keys on an alert number reaching a state; alert 117
appears once as a control fixture and alert 144 only as a locating label and as corroboration.
Requirement coverage is complete with no orphan tasks. All seven terminal states are named identically
in spec.md, plan.md, quickstart.md and tasks.md, and each is reachable and recorded.

The most consequential repair was **F-11**, which was not a documentation defect but a live verification
defect: every alerts query in the feature read one page of a 137-alert corpus, and on this repository
that reads as zero open alerts with exit 0. It sat in the T020 positive control, whose sole purpose is
to prove the gate is not blind. A control that can itself truncate certifies the gate while blind, so
the feature's single pass-on-emptiness condition rested on a query that could not fail. It now rests on
a corpus floor of 137, a rule total of 22, and the presence of a permanently `fixed` alert at the target
path, each a number measured against the live API rather than asserted.

---

## Adversarial Review #3

Final gate before implementation. Reviewer authored none of these artifacts. The question answered
here is narrow: **can an implementer execute tasks.md start to finish without getting stuck, misled,
or silently passing?**

The runbook was **executed, not read**. Every read-only command in tasks.md and quickstart.md was run
against the live repository and the live tree on 2026-07-30, and the regression guard of T007 was
built in a scratch copy and run against both unfixed and fixed source. What follows separates what
was RUN from what was READ, because Adversarial Reviews #1 and #2 both found defects that were
invisible on the page.

### Findings

| # | Severity | Finding | Evidence (executed) | Disposition |
|---|---|---|---|---|
| **G-01** | **HIGH** | **T014's SC-007 check cannot pass on correct code. Its `-B4` window is off by one and excludes the only line that carries the rule id.** `grep` matches the string literal `"OAuth state stored",`, which after the T010 edit sits below `logger.info(`, which sits below the four mandated comment lines. The rule id is on the first comment line, **five** lines above the match. `-B4` prints the four lines below it. The task's pass condition, "its output contains the literal `py/clear-text-logging-sensitive-data`", is therefore unsatisfiable by construction. This is the worst class of defect for this gate: an implementer who applies T009 and T010 exactly as written then fails their own verification, and there is no terminal state for "my instruction contradicts my check", so the path ends in an implicit abort. It is also re-run twice more, at T024 and at T032, so it fails three times. The same `-B4` sat in quickstart.md at the SC-007 check. | Applied T009+T010 to a scratch copy of `oauth_state.py` and ran the check verbatim. `-B4` prints lines 100-104 and `grep -c` for the rule id returns **0**. `-B5` prints lines 99-104 and returns **1**. | **FIXED** in tasks.md T014 and quickstart.md. Window widened to `-B6` (`-B5` plus one line of slack against a one-line drift in the comment), with the arithmetic stated inline in both files so it cannot be re-narrowed by a later reflow. |
| **G-02** | **HIGH** | **T030 is a pass-on-absence condition with no control, and it passes while blind.** T021 got a positive control (T020), a corpus floor, and an exit-code assertion. T030 asserts an equally load-bearing absence, "no alert of any rule newly appears on `oauth_state.py` or `secrets.py`", and got only the corpus floor. The floor proves the **fetch** worked. It proves nothing about the **path selector**, and the selector is what the absence is read from. The `AFTER` filter's own `jq` exit code was not captured either; the captured `JQ_RC` belongs to the preceding `CORPUS` call. | Ran T030 verbatim against the live 137-alert corpus with `.most_recent_instance.location.path` mistyped as `.locatio.path`. `jq` does **not** error: it returns `path: null` for all 137 entries and exits **0**. `gh exit=0`, `jq exit=0`, `corpus=137`, and the resulting open set contains **no** entry on `oauth_state.py` or `secrets.py`. **Every clause of T030's pass condition is satisfied by a read that sees nothing.** This is the governing rule of this review violated exactly: an absence taken as evidence without proving the read was working. | **FIXED** in tasks.md T030. Added `AFTER_RC` capture, a `null_paths` control that must be **0**, and an alert-117 path anchor that must return the literal string `src/lambdas/shared/auth/oauth_state.py`, the same immovable fixture T020 uses, for the same reason. Verified by running both: correct filter gives `null_paths=0` and a populated anchor path; the `.locatio` filter gives `null_paths=137` and `path: null`, so the broken read now fails loudly. |
| **G-03** | **HIGH** | **The likeliest terminal state skips the close-out and two checks the artifacts call unconditional.** T017 reads "Phases 6 to 8 are then not executed" on the `PENDING-BRANCH-ANALYSIS` branch. Phase 8 is T031 (FR-012 prior art), T032 (FR-013/SC-007 site comment, stated "unconditional across every terminal state") and T033 (SC-005 close-out, "exactly one terminal state is named"). Quickstart Step 1d calls `PENDING-BRANCH-ANALYSIS` "the likeliest ending rather than an edge case" for this feature, so on the most probable path the feature ends with FR-012, SC-005 and SC-007 unverified and no close-out written. T031 in particular reads only `research.md` and has no dependency on a merge whatsoever. | Read of T017 against the Phase 8 task bodies and against quickstart.md:238. No execution needed; the contradiction is between two sentences in the same file. | **FIXED** in tasks.md T017. Phases 6 and 7 are skipped; **Phase 8 still runs**, with T032's "merged file" clause reading against the committed file on the feature branch and that substitution recorded in evidence.md. |
| **G-04** | **HIGH** | **Six task-level failure paths say "stop" and name no terminal state.** The seven states cover every *gate* outcome and were verified reachable and distinct (below), but the abort risk had simply moved upstream of the gate. Specifically: T001 wrong Python ("stops the feature"); **T002 dirty `src/`/`tests/`**, with no stated action at all; T004's "premise is already gone: stop, record it"; T016's `make sast` non-zero; T023's "Discard, re-run T020 and T021", which unlike T019 carries **no bound** and loops forever on a persistently failing `gh` read; and a T026 `PATCH` failing for any reason other than permissions, which T028 is not scoped to accept. T002 is not hypothetical: the briefing states three sibling agents share this worktree and at least one of them (`001-ingestion-arn-logging`) edits `src/lambdas/ingestion/handler.py`, so a dirty `src/` is a *likely* observation, and T011, T015 and T016 all read a diff that would then be partly another feature's. | Read of the six task bodies against the terminal-state table. Corroborated by the live baseline showing alerts 148-150 on `src/lambdas/ingestion/handler.py`, the file a co-resident sibling is chartered to edit. | **FIXED** in tasks.md by a new "Routing for failures that are not gate outcomes" subsection under the terminal-state table. **No new state is introduced**; all six route to an existing one, with a catch-all making the routing exhaustive. T004's "premise already gone" routes to `CONFIRMED`, which its definition satisfies verbatim. Also corrected: T023's mixed-survivor precedence now explicitly triggers **T027**, because T026 running in the mixed case is a real dismissal and FR-007/SC-006 require a registry entry for any dismissal regardless of the state finally recorded. |
| **G-05** | **HIGH** | **The `security_events` misreading that convention §5b exists to prevent survives in two normative places.** F-06 sanitised quickstart.md and spec.md's FR-008, but plan.md's terminal-state table still defined the `BLOCKED-ON-OWNER` trigger as "the implementing agent lacks `security-events: write`", and spec.md's Assumptions still opened "Dismissing a code scanning alert requires `security-events: write`" as a flat premise with no carve-out. plan.md is, by its own AR#2 X5, "the artifact the implementer reads first". An implementer applying that trigger reads `gh auth status`, finds scopes `gist, read:org, repo, workflow`, sees no `security_events`, and lands in `BLOCKED-ON-OWNER`, which is the wrong terminal state, on a repository where the dismissal is available. §5b records that the sibling made this exact mistake once already. | Ran the T006 probe: scopes `gist, read:org, repo, workflow`; `visibility: public`; `permissions.admin: true`, `push: true`. Convention §5b (lines 144-164) read directly: `security_events` is required "only on **private** repositories". So the plan.md trigger and the observed environment together produce a false `BLOCKED-ON-OWNER`. | **FIXED** in plan.md (trigger restated as the §5b read-only probe with the public-repository carve-out) and in spec.md Assumptions (premise corrected, permission settled by probe rather than by attempted dismissal). |
| **G-06** | **MEDIUM** | **`$CHANGE_SHA` lives only in a shell across a wait bounded at 7 days.** T017 exports it; T019's freshness proof is the only consumer and may run days later; nothing instructs persisting it except on the `PENDING-BRANCH-ANALYSIS` branch, where what gets written is the gate query rather than the SHA. A lost `$CHANGE_SHA` makes T019 unrunnable and strands the feature between `PENDING-BRANCH-ANALYSIS` and `BLOCKED-NO-ANALYSIS`. `$RULE`, `$FILE` and `$REPO` have the same lifetime problem but are self-catching: an empty `$RULE` makes T020's `rule_total` **0** and its control empty, which fails loudly. `$CHANGE_SHA` is not self-catching, because an empty one makes the `compare` call 404 rather than silently mis-answer. | Read, plus the observation that T020's floors do catch the environment-variable case: an unset `$REPO` yields `repos//code-scanning/alerts` and a non-zero `gh` exit. | **FIXED** in tasks.md T017: `$CHANGE_SHA` is recorded into `evidence.md`, on every path and not only the pending one. |
| **G-07** | **LOW** | **The verdict of the Stage 7 Cross-Artifact Analysis overclaims.** It states "All seven terminal states are named identically in spec.md, plan.md, quickstart.md and tasks.md." They are not. `CONFIRMED`, `REFUTED-DISMISSED` and `REPORTED-FOREIGN-SINK` do not appear as literal strings in spec.md at all; spec.md's Decision Gate uses the classification vocabulary "Confirmed" / "Refuted" / "Not Confirmed, and not this feature's" and names only the four `BLOCKED-*`/`PENDING-*` states literally. | `grep -o` for the seven names across all four files: plan.md, quickstart.md and tasks.md return all seven; spec.md returns four. | **Not fixed.** T023's classification table bridges the two vocabularies explicitly and tasks.md is the executed document, so nothing is ambiguous at execution time. Recorded because a verdict line that overstates its own sweep is the thing a fourth reviewer would trust. |
| **G-08** | **LOW** | **T011's two thresholds disagree.** Its pass condition is "every hunk header's start line is **below 122**"; its remediation sentence is "any hunk at or beyond line **154** means `validate_oauth_state()` was edited: revert it". A hunk starting at line 130 (inside `get_oauth_state()`) fails the pass and matches no remediation. | Read. Confirmed against the live file: `def get_oauth_state` at 122, `def validate_oauth_state` at 154. | **Not fixed.** The stricter threshold governs and an edit at 130 is out of scope for this feature anyway, so both readings reject it. Recorded only. |
| **G-09** | **LOW** | **T016 greps a configuration path that does not exist.** `git status --short -- .github/ .semgrep* pyproject.toml` includes `.semgrep*`; no such file or directory exists in the repository. The FR-010 surface is still fully covered (CodeQL's config is `.github/codeql/codeql-config.yml`, inside `.github/`; bandit's and ruff's are in `pyproject.toml`; and `make sast` invokes `semgrep scan --config auto` with no local config at all), so the dangling glob costs nothing. | `ls -d .semgrep*` → "No such file or directory". `make sast` output confirms `--config auto`, Community registry, 1032 rules. | **Not fixed.** No-op, and removing it would weaken the check if a `.semgrep.yml` is ever added. |

### What was RUN, and what it returned

Executed against the live repository and the live tree, 2026-07-30. Everything in this table is real
output, not a restatement of the artifact.

| Command | Result | Verdict |
|---|---|---|
| T001 `python --version` in `.venv` | `Python 3.13.0` | PASS |
| T003 `pytest tests/unit/auth/ -q` | `30 passed`, `pytest exit=0` | PASS, baseline confirmed at the documented figure |
| T004 paginated baseline | `gh exit=0 jq exit=0 corpus=137`; open set `{150,149,148,147,144}`; 144 at `oauth_state.py:104` | PASS, matches the recorded observation exactly |
| T005 alert 144 snapshot | `state: open`, `fixed_at: null`, `start_line: 104`, `code_flows: 0`, `commit_sha c010178` | PASS, `code_flows: 0` confirmed, so the "no claim about the taint path" position holds |
| T006 permission probe | scopes `gist, read:org, repo, workflow`; `visibility: public`; `permissions.admin/push: true` | PASS, resolves **available** |
| **T007 + T008 guard, built and run against UNFIXED source** | `1 failed, 15 passed`, `pytest exit=1`, sole failure `test_log_context_excludes_provider` on `assert not hasattr(records[0], "provider")`, with `where True = hasattr(<LogRecord ...>, 'provider')` | **PASS. The guard is genuinely non-vacuous, and it fails on precisely the assertion T008 predicts.** This is the single most important thing this review verified, and it holds. |
| T009 + T010 applied to a scratch copy, then `ruff check` with the repo's rule selection | `All checks passed!`, `ruff exit=0`, no `F841` | PASS, the deletion-not-orphaning requirement is satisfiable |
| The same guard re-run against the FIXED source | `1 passed` | PASS, so the guard is red-then-green, not red-forever |
| T013 `ruff format --check` + `ruff check` on the two real files | `2 files already formatted`, `All checks passed!`; `ruff 0.15.14` matches `required-version = "==0.15.14"` | PASS, no version-skew trap |
| **T014 SC-007 check on the fixed scratch copy** | `-B4` window is lines 100-104; rule id occurrences: **0**. `-B5`: **1**. Pragma grep: `exit 1` | **FAIL → G-01, fixed** |
| T016 `make sast` | `Findings: 0 (0 blocking)`, 478 rules, 164 targets, `make sast exit=0` | PASS, the substitute gate is achievable |
| Invariant 3, `bash scripts/check-banned-terms.sh` | `exit=1`; `FAIL: 17 total banned-term matches`, 15 + 2 across two legacy framework names; matches inside `001-oauth-provider-taint`: **0** | PASS, the figure and the split are both exactly as documented, and this directory is clean |
| T018 analyses lookup | `gh exit=0`, five `/language:python` analyses, `created_at` strictly descending, newest `id 1551613089` at `c010178` | PASS, and the newest-first property the unpaginated design rests on is confirmed |
| **T020 positive control** | `gh exit=0 jq exit=0 corpus=137 rule_total=22`; `control=[{"number":144,"state":"open"},{"number":117,"state":"fixed"}]` | **PASS on all four floors, byte-identical to the recorded value.** Confirmed as the strongest control in the artifact set. Not weakened. |
| T021 gate query (pre-change, so expected non-empty) | `jq exit=0`; `gate=[{"number":144,"start_line":104,"commit_sha":"c010178..."}]` | PASS, the query returns the finding it is supposed to see |
| T022 attribution at the analyzed commit | `gh exit=0 bytes=10550`, `base64 exit=0`, `grep exit=0`; defs at 50, 59, 122, 154, so `store_oauth_state()` spans **59-121** and alert 144 at line 104 attributes **inside** | PASS |
| quickstart 3b pipeline variant of the same | `PIPESTATUS=0 0 0` | PASS today; the X9 exposure stands but is not triggered |
| **T030 with a mistyped path selector** | `jq exit=0`, `corpus=137`, all 137 entries `path: null`, resulting set clean of both target files | **FAIL → G-02, fixed** |
| Invariant 7, unpaginated open read | `0`, `exit=0` on a repository with five open alerts | Trap confirmed exactly as stated |
| Invariant 7, default page composition | `n=30`, numbers **180 down to 151**, all `state: fixed`; alert 144 present: **0** | The "past the end of page one" claim is precisely right |
| Invariant 7, `per_page=100` page one | `{"max":180,"min":59,"n":100,"open":[150,149,148,147,144]}` | Confirmed, with a nuance recorded below |
| `--slurp` with `--jq` | `the --slurp option is not supported with --jq or --template` | Confirmed |
| `--paginate` without `--slurp`, per-page collector | prints `[]` **twice** | Confirmed |
| `gh api --arg` | `unknown flag: --arg`; `gh version 2.89.0` | Confirmed, AR#2 X1 was a real defect |
| T031 prior-art grep | `16` matching lines, `grep exit=0` | PASS, floor of 3 cleared |
| T027 registry target | `docs/reference/TECH_DEBT_REGISTRY.md` exists, highest id `TD-023` | PASS when checked. **OBSOLETE 2026-07-31**: registry deleted by `001-constitution-prune`; T027 now targets `CLEANUP-BOARD.html` and allocates no id |
| `.github/workflows/pr-checks.yml:62` | `run: ruff check src/ tests/` | Citation is accurate to the line |
| Convention §5a / §5b | lines 132 and 144 | Citations accurate |

### The seven terminal states

Each was checked for reachability, distinctness, and gaps between them.

| State | Reachable? | Distinct? | Notes |
|---|---|---|---|
| `CONFIRMED` | Yes, T024, and now also from T004's "premise already gone" via G-04 routing | Yes | The only pass-on-emptiness state. Guarded by T020's control and the corpus floor, both re-verified by execution. |
| `REPORTED-FOREIGN-SINK` | Yes, T025 | Yes | Also the recorded state for the mixed case per T023. `validate_oauth_state()` at 154-260 is a live, verified candidate for producing it. |
| `REFUTED-DISMISSED` | Yes, T026+T027; T006 probed *available*, so the `PATCH` is not blocked | Yes | Registry obligation now also attaches when T026 runs inside the mixed case (G-04). |
| `BLOCKED-ON-OWNER` | Yes, T028 | Yes | Was reachable **for the wrong reason** from plan.md and spec.md until G-05. Now entered only from the §5b probe or a failed `PATCH`, the latter widened past permission-only failures. |
| `BLOCKED-NO-ANALYSIS` | Yes, T029 | Yes, the 7-day clock starts at `main` | Now also the exit for T023's previously unbounded discard loop (G-04). |
| `BLOCKED-REGRESSION` | Yes, T029 | Yes | Now also absorbs T001, T002 and T016 failures (G-04). Correctly does **not** trigger on repo-wide count movement. |
| `PENDING-BRANCH-ANALYSIS` | Yes, T017 | Yes, the clock has not started | Quickstart calls it the likeliest ending, and it was skipping the entire close-out until G-03. |

**Verdict on the set: seven states, all reachable, all distinct, and after G-03 and G-04 there are no
remaining paths that fall between them.** The gaps found were not gaps *between* the states; they
were failures *upstream* of the gate that named no state, which is the same implicit abort at a
different altitude. That failure mode has now occurred twice in this feature (once as F-01, once as
G-04), which argues the routing subsection should be inherited by siblings rather than re-derived.

### Highest-risk task

**T009 and T010, taken as one edit.** Not because the edit is hard, since it is four deleted lines and a
four-line comment, but because it is the only irreversible-in-practice step whose verification
was broken. The T014 check that proves T010 landed correctly could not pass (G-01), and it is
re-run at T024 and T032, so the same false negative fires three times across the feature. A second
factor: T009's "anchor by content, not by line number" instruction is correct and necessary, because
the mandated comment lands in the same place as the deleted lines and the net line shift is near
zero, which makes line-number anchoring look like it works right up until it does not.

Nothing else in the feature edits code. Everything downstream is observation.

### Most likely source of rework

**T002 failing, or its check being skipped and the failure surfacing later at T015 and T016.** Three
sibling agents share this worktree; `001-ingestion-arn-logging` is chartered on
`src/lambdas/ingestion/handler.py`, which the live baseline confirms carries alerts 148-150. A dirty
`src/` makes T011's hunk-header check, T015's confined-diff check and T016's `git diff --name-only`
"exactly two files" check all read a diff that is partly another feature's, and the natural but wrong
reaction is to relax the pass condition rather than to stop. Second most likely: a merge that does
not happen, landing the feature in `PENDING-BRANCH-ANALYSIS` and, before G-03, skipping the close-out
that records it.

### Ordering hazards

- **T007 before T009 is the load-bearing order and must not be relaxed.** Verified by execution: the
  guard fails on unfixed source with the exact predicted assertion. Run in the other order, the guard
  is green from birth and proves nothing. Note that quickstart Step 1 still applies the source edit
  (1a) before the test (1b); that disagreement was recorded as deliberate at Stage 7 and tasks.md is
  the executed document, so it stands.
- **T020 strictly before T021, and no re-fetch between them.** Enforced in the text, and correct.
- **T019 before T021.** A stale analysis decides nothing.
- **T006 before anything in Phase 7.** Correct, and now also correct in plan.md and spec.md (G-05).
- **T017's phase skip is itself an ordering hazard**, resolved by G-03: Phase 8 is not downstream of
  a merge.
- **The gap between T017 and T019 spans up to 7 days and one or more shell sessions.** Resolved by
  G-06 for `$CHANGE_SHA`. `$REPO`, `$RULE` and `$FILE` are self-catching via T020's floors.

### Corrections to the campaign facts and to the artifacts

Recorded because a briefing that is never wrong is a briefing nobody checked.

1. **The briefing's canonical query differs from the one tasks.md mandates, and both work.** The
   briefing's form is `...&state=open&per_page=100` with `jq 'add | length'`; tasks.md drops
   `state=open` and uses `jq '[.[][]] | length'`. Both return **137** here, which is initially
   surprising: `add` on the slurped array of pages and `[.[][]]` are equivalent, and `state=open`
   turns out **not** to filter the corpus count in this call. tasks.md's form is the right one to
   keep, because the T020 control needs `fixed` alerts in the corpus and `state=open` would remove
   alert 117, the control's anchor. Worth stating explicitly so a future reader does not "harmonise"
   them toward the briefing.
2. **"`per_page=100` still drops alerts 22-27" is true, but the sharper statement is that it does
   not drop any *open* alert.** Measured: page one at `per_page=100` returns
   `open:[150,149,148,147,144]`, the complete open set. So the gate query T021 would be *accidentally*
   correct at `per_page=100` today; it is the **T020 control** that genuinely requires pagination,
   because alert 117 sits at number 117 < 59 and falls off page one. This makes F-11's judgement that
   the control was the worst placement exactly right, and it means the pagination requirement must
   never be justified to a future reader on the grounds that the gate needs it. It does not, today,
   and that argument would collapse the moment someone tested it.
3. **The briefing says "Unpaginated reads return ZERO open alerts while FIVE are open."** Confirmed,
   and the mechanism is worth recording because it is not "the API hides open alerts": the default
   page is 30 alerts ordered by descending number, 180 down to 151, and **all thirty are `fixed`**.
   The open alerts are simply lower-numbered. This is stable only while no new alert is created; a
   sibling opening a new high-numbered alert would move open alerts onto page one and make the
   unpaginated read look correct again. The corpus floor is what keeps that from mattering.
4. **The briefing's line-number citation for the T007 insertion point is accurate**
   (`TestStoreOAuthState` at line 37), as are T009's `def` at 59, deletions at 99-101 and 105,
   `get_oauth_state` at 122, `validate_oauth_state` at 154, `safe_provider_validated` at 253 and the
   `extra` at 258, and the persisted `"provider": provider` at 87. All ten verified against the live
   file. This is unusual for this campaign and is worth saying.
5. **`pytest -q` does not produce quiet output in this repository.** `addopts` in `pyproject.toml`
   carries `-v`, and `log_cli = true`, so T003, T008 and T012 print per-test lines and live log
   output. The summary line is still `N passed`, so no pass condition breaks, but an implementer
   expecting a one-line result will not get one.
6. **The briefing's claim that "`make validate` cannot pass on this tree" is correct**, and the
   figure is exact: 17 matches, 15 + 2, none in this directory. `make sast` as the substitute is
   achievable: it returned 0 findings and exit 0 in 4 minutes.

### Adjacent defects, outside this feature's scope. Carded, not fixed.

1. **`validate_oauth_state()` at `oauth_state.py:253-258` carries the identical sanitize-in-place
   shape that this feature is deleting from `store_oauth_state()`, and it is not currently reported
   by any open alert.** FR-004 correctly freezes it and `REPORTED-FOREIGN-SINK` correctly exists for
   it. But it is worth carding on its own: the same shape at lines 202-217 and 222-238 logs
   `expected`/`received` pairs for both provider and `redirect_uri`. A future CodeQL query update
   that starts reporting it will spawn alerts on a file this campaign has just churned.
2. **Constitution §9 still names `docs/TECH_DEBT_REGISTRY.md`**, relocated by `f8db8d2` (PR #668).
   Already noted in T027 and quickstart 4b as carded. Confirmed still stale. **RESOLVED
   2026-07-31** by retirement rather than repair: `001-constitution-prune` deleted §9 and the
   registry file, so there is no path left to be stale.
3. **Five stale sibling citations (F-03)** remain, deliberately, pending the campaign-wide sweep.
   Not re-derived here.
4. **`make sast` only scans files tracked by git** ("Scan was limited to files tracked by git", from
   the live run). Both files this feature touches are tracked, so nothing is missed here, but a
   feature that adds a brand-new untracked source file would get a clean SAST result on a file that
   was never scanned. That is a repository-wide gate weakness, not this feature's.
5. **`.github/workflows/pr-checks.yml` runs CodeQL as job `codeql` / name `Analyze`, and it is not a
   required status check.** The artifacts already rely on this being true (FR-009 refuses PR-check
   evidence because of it). Carded as a repository observation, not a defect to fix here.

### Verdict

Five HIGH findings, one MEDIUM and three LOW. Two of the HIGH findings were live verification
defects rather than documentation drift, and both were found by running the runbook rather than
reading it:

- **G-01** made the SC-007 check unsatisfiable on correct code, at three separate call sites.
- **G-02** left the feature's second pass-on-absence condition certifying SC-003 while blind, on a
  broken read that `jq` reports as successful. A mistyped field name in that filter returns
  `path: null` for all 137 alerts, exits 0, satisfies the corpus floor, and produces a clean result.

Both are fixed and both fixes were verified by execution, not by inspection. G-03, G-04 and G-05 are
fixed in the artifacts. G-06 is fixed. G-07, G-08 and G-09 are recorded and deliberately not fixed.

What holds up: the T007 regression guard is genuinely non-vacuous and was proved so by building and
running it against both unfixed and fixed source; the T020 positive control is exactly as strong as
claimed and its three floors reproduce byte-for-byte against the live API; every line-number citation
into `oauth_state.py` is accurate; the pagination invariant is correct in every particular including
the ones that are counter-intuitive; and requirement coverage remains 14/14 and 7/7 with no orphan
tasks. The T018 decision to leave the analyses endpoint unpaginated is correct and was re-verified:
five consecutive `/language:python` analyses, strictly descending `created_at`.

**READY FOR IMPLEMENTATION**
