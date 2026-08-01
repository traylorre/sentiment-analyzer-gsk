# Evidence: Close CodeQL alert 144 (OAuth provider taint)

**Feature**: `001-oauth-provider-taint` | **Executed**: 2026-07-31
**Executed document**: [tasks.md](tasks.md) | **Runbook**: [quickstart.md](quickstart.md)

This file is the record required by T017, T023 and T033. It carries the baseline set, the change SHA,
the filled-in gate query, and exactly one terminal state.

---

## Terminal state

**`PENDING-BRANCH-ANALYSIS`**

That is the whole of the recorded state. Six other states exist in tasks.md's table and none of them
is recorded here; where they are named below it is to record that they were considered and rejected,
never as a second classification.

Inherited from `specs/001-ingestion-arn-logging/codeql-logging-convention.md` **§5a** via FR-008,
which calls it "the normal ending, not an edge case". Reported as **neither done nor failed**.

**The observation it rests on.** Closure is read from a default-branch CodeQL analysis (FR-009,
convention §3 Trap 3). The change is committed on the feature branch and has not been pushed, so no
qualifying analysis can exist:

```
$ git ls-remote --heads origin 001-oauth-provider-taint
(no output)
ls-remote exit=0
```

An exit of 0 with no matching ref is the read succeeding and finding nothing, which is the whole
distinction: the branch is absent from the remote, not unreadable. Pushing is gated on the repository
owner and was not attempted.

**Why not `BLOCKED-NO-ANALYSIS`.** That state's 7-day clock starts when `$CHANGE_SHA` lands on
`main`. Nothing has landed, so the clock has not started (tasks.md T017; quickstart Step 1d).

**Why not `BLOCKED-ON-OWNER`.** That state requires a survivor to have been observed at the gate and
the dismissal permission to be absent. No survivor has been observed, because the gate was not
evaluated, and the T006 probe resolved to **available** in any case.

**Why not `CONFIRMED`.** FR-009 and SC-002 admit only default-branch evidence. The local unit suite
being green is not closure evidence and is not treated as any.

---

## `$CHANGE_SHA`

Recorded here rather than left in a shell, per T017 as amended by Adversarial Review #3 finding
**G-06**: T019's freshness proof is its only consumer and the wait it bounds outlives any shell.

| Field | Value |
|---|---|
| Feature-branch commit | **`f264c1d`** (`fix(001): remove the provider-derived value from the OAuth state log context`) |
| GPG signature | `G` (good), per `git log --format='%h %G? %s'` |
| Branch | `001-oauth-provider-taint`, parent `1d68832` |
| `$CHANGE_SHA` (merge commit on `main`) | **ABSENT.** Not yet pushed, no PR, no merge commit exists. |

`$CHANGE_SHA` must be filled in with the **merge commit SHA on `main`**, not with `f264c1d`, at the
moment the change lands. T019 compares `$CHANGE_SHA...$ANALYZED_SHA` and a feature-branch SHA that
never reached `main` makes that call 404 rather than answer wrongly.

---

## Phase execution record

| Phase | Status |
|---|---|
| 1. Preconditions and baseline (T001-T006) | Executed, all pass |
| 2. Regression guard written first (T007, T008) | Executed, guard proven failing on unfixed code |
| 3. Production change (T009-T011) | Executed |
| 4. Local gates (T012-T016) | Executed, all pass |
| 5. Land the change (T017) | Commit executed; push, PR and merge **not** attempted (owner-gated) |
| 6. Decision gate (T018-T023) | **Not executed.** No default-branch analysis can exist. |
| 7. Terminal branches (T024-T030) | **Not executed.** No classification was made, so no branch is reachable. |
| 8. Durability and close-out (T031-T033) | Executed. Phase 8 runs on this branch per Adversarial Review #3 finding **G-03**. |

Phases 6 and 7 are skipped and Phase 8 still runs. T031 reads only `research.md` and has no
dependency on a merge; T032 and T033 are declared unconditional across every terminal state, and this
is the state quickstart Step 1d calls the likeliest ending, so skipping Phase 8 here would leave
FR-012, FR-013, SC-005 and SC-007 unverified on the most probable execution path.

### T032 substitution, recorded explicitly

SC-007 is stated against the **merged file**. No merged file exists. T032 was therefore run against
**the committed file on the feature branch**, read with `git show HEAD:...` rather than from the
working tree, so the check is against committed bytes and not against an unstaged edit. tasks.md T017
prescribes exactly this substitution for this state and requires it be recorded here. It is recorded
here.

---

## T004 baseline set, verbatim

Recorded as a **set**, never as a count (SC-003 is an attribution test). Read 2026-07-31 with the
mandatory paginated shape from invariant 7.

```
gh exit=0 jq exit=0 corpus=137
baseline=[{"number":150,"rule":"py/clear-text-logging-sensitive-data","path":"src/lambdas/ingestion/handler.py","line":276},{"number":149,"rule":"py/clear-text-logging-sensitive-data","path":"src/lambdas/ingestion/handler.py","line":271},{"number":148,"rule":"py/clear-text-logging-sensitive-data","path":"src/lambdas/ingestion/handler.py","line":264},{"number":147,"rule":"py/bad-tag-filter","path":"scripts/regenerate-mermaid-url.py","line":82},{"number":144,"rule":"py/clear-text-logging-sensitive-data","path":"src/lambdas/shared/auth/oauth_state.py","line":104}]
```

Corpus floor of 137 met exactly. The set is `{144, 147, 148, 149, 150}`, matching the value recorded
at authoring time, with 144 at `oauth_state.py:104`. The premise is present: the complete read
contains an entry whose `path` is `$FILE` and whose `rule` is `$RULE`, so T004's "premise already
gone" routing to `CONFIRMED` does **not** apply.

Siblings legitimately move this set. `001-ingestion-arn-logging` owns 148-150,
`001-bad-tag-filter-dead-suppression` owns 147, and `001-codeql-coverage` is expected to raise the
total on purpose. The count is not the test.

### T005 locating snapshot of alert 144

```
gh exit=0
{"code_flows":0,"commit_sha":"c01017888484bd5a0fdec9a32ded42378829f6dc","dismissed_reason":null,"fixed_at":null,"number":144,"path":"src/lambdas/shared/auth/oauth_state.py","start_line":104,"state":"open"}
```

`code_flows` is `0`, which is why no artifact here claims to know the taint path. Nothing downstream
keys on this alert's state; 144 is a locating label.

### T006 dismissal-permission probe, read-only

```
  - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
gh exit=0
perm={"permissions":{"admin":true,"maintain":true,"pull":true,"push":true,"triage":true},"visibility":"public"}
```

Resolved **available**: `visibility` is `public`, `permissions.push` is `true`, and the scope list
contains `repo`, which subsumes `public_repo`. The absent `security_events` scope is **not** a
blocker; GitHub requires it only on **private** repositories (convention §5b). Established by a
read-only probe, never by attempting a `PATCH`, which mutates alert state and cannot be cleanly
reverted.

---

## The gate query, filled in and ready to run

Required by T017 so the check is mechanical the moment the change lands. `$RULE` and `$FILE` are
already substituted. Run the control first, then the gate, against the **same** file. Do not re-fetch
between them.

```bash
export REPO=traylorre/sentiment-analyzer-gsk
export RULE=py/clear-text-logging-sensitive-data
export FILE=src/lambdas/shared/auth/oauth_state.py
export ALERTS_JSON=/tmp/oauth-alerts-gate.json

# T018 first: locate the newest default-branch python analysis.
# Deliberately unpaginated. The endpoint is newest-first, this wants exactly the
# newest, and emptiness here is a FAILURE condition, so truncation cannot render
# as clean. Do not "fix" this into a paginated query.
AN=$(gh api "repos/$REPO/code-scanning/analyses?ref=refs/heads/main&per_page=5" \
  --jq '[.[] | {id, commit_sha, created_at, analysis_key, category}]')
RC=$?; printf 'gh exit=%s\n%s\n' "$RC" "$AN"
export ANALYZED_SHA=<commit_sha of the newest /language:python analysis>

# T019 freshness proof. A result predating the change decides nothing.
# CHANGE_SHA is the MERGE COMMIT ON main, not f264c1d.
export CHANGE_SHA=<merge commit sha on main>
ST=$(gh api "repos/$REPO/compare/$CHANGE_SHA...$ANALYZED_SHA" --jq '.status')
RC=$?; printf 'gh exit=%s status=%s\n' "$RC" "$ST"
# Accept only "ahead" or "identical". Bound: 7 days from CHANGE_SHA landing on
# main, then BLOCKED-NO-ANALYSIS via T029.

# T020 positive control, FIRST. The gate's pass condition is emptiness, so it is
# worthless without proof the query can return anything at all.
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

# T021 gate, over the SAME file the control just validated.
GATE=$(jq -c --arg r "$RULE" --arg f "$FILE" \
  '[.[][] | select(.state == "open")
          | select(.rule.id == $r)
          | select(.most_recent_instance.location.path == $f)
          | {number, start_line: .most_recent_instance.location.start_line,
             commit_sha: .most_recent_instance.commit_sha}]' "$ALERTS_JSON")
JQ_RC=$?; printf 'jq exit=%s\ngate=%s\n' "$JQ_RC" "$GATE"
```

**T020 pass, all four**: `gh exit=0` and `jq exit=0`; `corpus` at least **137**; `rule_total` at
least **22**; and `$CTRL` containing **alert 117**, which is `state: fixed` at this path and is
therefore an immovable anchor that stays satisfied whatever the outcome. `state=open` is deliberately
**not** in this query, because that filter would remove alert 117 and destroy the control.

**T021 pass for `CONFIRMED`**: T020 passed on all four floors, `jq exit=0`, and `$GATE` is exactly
`[]`. A **blank** `$GATE` is a failed filter, not a closed alert, and is discarded rather than
classified. Emptiness is a pass only because the control proved, on the same bytes, that a finding of
this rule at this path is visible to this query when one exists.

**Never** run the alerts query unpaginated. Measured on this repository: unpaginated it reports zero
open alerts and exits 0 while five are open, because the default page is 30 alerts ordered by
descending number and all thirty are `fixed`. `per_page=100` alone is not a fix either: page one at
that size drops alert 117, which is the control's anchor.

If `$GATE` is non-empty, attribute every survivor at `$ANALYZED_SHA` per T022 before acting on it. A
survivor inside `store_oauth_state()` is this feature's, and routes to T026 plus a
`docs/reference/TECH_DEBT_REGISTRY.md` entry whose `TD-` id is read from the registry's then-highest
entry at that moment. A survivor outside it, most likely the FR-004-frozen `validate_oauth_state()`
sink at lines 253-258, is **reported and never dismissed**.

---

## Local gate results

Every one of these was run, not read. Output is verbatim.

| Task | Command | Result |
|---|---|---|
| T001 | `python --version` in `.venv` | `Python 3.13.0` |
| T002 | `git status --short -- src tests` | `0` lines. Clean. |
| T003 | `pytest tests/unit/auth/ -q` | `30 passed`, `pytest exit=0` |
| T008 | `pytest tests/unit/auth/test_oauth_state.py -q`, **before** the production edit | `1 failed, 15 passed`, `pytest exit=1`, sole failure `test_log_context_excludes_provider` on `assert not hasattr(records[0], "provider")` |
| T011 | `git diff -U0 ... \| grep -E '^@@'` | `@@ -99,3 +99,4 @@` and `@@ -105 +105,0 @@`, `grep exit=0`. Both below 122. |
| T012 | `pytest tests/unit/auth/ -q` | `31 passed`, `pytest exit=0` |
| T013 | `ruff format` then `ruff check` | `2 files left unchanged`, `All checks passed!`, `ruff exit=0`. No `F841`. |
| T014 | SC-007 grep, `-B6` window | Rule id present at line 99, `grep exit=0`. Pragma grep `exit=1`. |
| T015 | `git diff` byte count and changed-line count | `diff bytes=946`, 10 lines matching `^[-+]` (8 real, 2 diff headers) |
| T016 | `git status --short -- .github/ .semgrep* pyproject.toml` | Prints nothing. No analysis config, query pack, severity or path exclusion touched. |
| T016 | `make sast` | `Findings: 0 (0 blocking)`, 478 rules, 164 targets, `make sast exit=0` |
| T031 | `grep -c '8424cbd\|0e7a375\|ebcc2f4' research.md` | `16`, `grep exit=0`. Floor of 3 cleared. |
| T032 | SC-007 grep against `git show HEAD:` output | Rule id present, `research.md` pointer present, pragma grep `exit=1` |

**T008 is the load-bearing one.** The guard was written and proven failing before the production edit
existed, on precisely the assertion T008 predicts. It asserts on the `LogRecord` attribute rather
than on `caplog.text`, because the production formatter renders no `extra` keys and a text assertion
would have passed on unfixed code. Red first, then green: that is the only thing that shows the guard
is not decoration.

**`make validate` was not run as a gate**, per invariant 3. It chains `check-banned-terms`, which
exits 1 on pre-existing matches in other features' spec directories. `make sast` is the substitute
and it passed. Repairing other features' directories is a different feature's scope.

---

## Diff, confined

Two files, plus this one.

- `src/lambdas/shared/auth/oauth_state.py`: the `safe_provider` assignment **deleted** (not orphaned,
  which would fail `ruff check` with `F841` and block the required `Lint` context), the
  `"provider": safe_provider` entry deleted from the `extra` dict, and the four-line FR-013 comment
  added above `logger.info(`. Nothing substituted for the removed value: not a literal, not an
  allowlist-selected constant, not a boolean (FR-001, FR-002).
- `tests/unit/auth/test_oauth_state.py`: `import logging` added, one method
  `test_log_context_excludes_provider` added to `TestStoreOAuthState`. No existing assertion edited
  (FR-011, SC-004).

**FR-003**: the `put_item` item dict, including the deliberately persisted `"provider": provider` at
line 87, the returned `OAuthState`, and the `code_verifier` generation appear in no `+`/`-` line.
Behavior outside the log call is unchanged.

**FR-004**: `validate_oauth_state()` is untouched. Its `safe_provider_validated` and its
`extra={"provider": safe_provider_validated}` carry the identical sanitize-in-place shape that left
alerts 22-25 with `fixed_at` null to this day, and this feature does **not** fix it. Both diff hunks
start below line 122, which is the next top-level `def` after the sink.

**FR-010**: nothing suppressed. No `# nosec`, `# noqa`, `# lgtm`, no CodeQL pragma, no severity
change, no path exclusion, no analysis configuration touched.

---

## What is outstanding

1. Push the branch, open a PR, merge. Both are gated on the repository owner and were not attempted.
2. Record the **merge commit SHA on `main`** into the `$CHANGE_SHA` row above.
3. Wait for a default-branch `/language:python` analysis and prove freshness with T019's `compare`.
4. Run the control and the gate above, in that order, and classify **once** per T023.
5. Run the T030 SC-003 attribution recount, which carries its own two controls: `null_paths` must be
   exactly `0` and the alert-117 path anchor must return
   `src/lambdas/shared/auth/oauth_state.py`. A corpus floor proves the fetch worked and proves
   nothing about the path selector; mistyping `.location` as `.locatio` returns `null` for every
   alert, exits 0, satisfies the floor and produces a clean result.
6. Record the resulting terminal state, replacing `PENDING-BRANCH-ANALYSIS` with exactly one of
   `CONFIRMED`, `REPORTED-FOREIGN-SINK`, `REFUTED-DISMISSED`, `BLOCKED-ON-OWNER`,
   `BLOCKED-NO-ANALYSIS` or `BLOCKED-REGRESSION`.

The T030 set difference is not recorded here because T030 was not run; it belongs to Phase 7, which
is unreachable in this state.
