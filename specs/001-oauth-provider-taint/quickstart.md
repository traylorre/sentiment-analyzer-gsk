# Verification Runbook: Close CodeQL alert 144 (OAuth provider taint)

**Feature**: `001-oauth-provider-taint` | **Date**: 2026-07-30 | **Plan**: [plan.md](plan.md)

Everything needed to apply the change, evaluate the decision gate exactly once, and land in one of
the **seven** terminal states. Commands are copy-pasteable. `REPO` is set once and reused.

```bash
export REPO=traylorre/sentiment-analyzer-gsk
export RULE=py/clear-text-logging-sensitive-data
export FILE=src/lambdas/shared/auth/oauth_state.py
source .venv/bin/activate   # required before any python or pytest
```

The seven states are `CONFIRMED`, `REPORTED-FOREIGN-SINK`, `REFUTED-DISMISSED`, `BLOCKED-ON-OWNER`,
`BLOCKED-NO-ANALYSIS`, `BLOCKED-REGRESSION` and `PENDING-BRANCH-ANALYSIS`. The last is inherited
from `specs/001-ingestion-arn-logging/codeql-logging-convention.md` §5a via FR-008 and is, in that
document's words, "the normal ending, not an edge case": it is where this runbook stops if the change
has not landed on `main`. See Step 1d. plan.md's terminal-state table and tasks.md carry the same
seven.

### Read this before running any alerts query

**An unpaginated code-scanning alerts query silently truncates, and the truncation renders as
CLEAN.** Measured on this repository 2026-07-30: `gh api repos/$REPO/code-scanning/alerts` filtered
to open alerts returns **zero** results and exits **0**, because the default page size is 30 and the
corpus is **137**, with the open alerts at numbers 144 to 150 sitting past the end of page one.
`per_page=100` is not a fix either: page one at that size spans alert numbers 180 down to 59, which
drops alerts 1 and 22 to 27, and 22 to 27 are the `secrets.py` sanitize-in-place sites this feature
reasons about throughout.

Every alerts query below therefore uses `--paginate --slurp` into a file, filtered by standalone
`jq` with its own exit code, and asserts a **corpus floor** before anything derived from it is
believed. Two mechanical notes, both verified by running them: `--slurp` is rejected in combination
with `--jq`, which is why the response goes to a file; and `--paginate` without `--slurp` applies
`--jq` once per page, so a per-page `[...]` collector prints one array per page and a two-page
response would print `[]` twice, satisfying an "output is `[]`" pass condition twice over while
telling you nothing.

---

## Step 0a. Record the baseline, before touching anything

```bash
# SC-003 baseline. Record the SET, never the count: three sibling features are
# landing in this window and each legitimately moves it.
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

Accept the baseline only if `gh exit=0`, `jq exit=0` and `corpus` is at least **137** (measured
2026-07-30; the figure only rises, because code scanning alerts are never deleted). Below the floor
the read was truncated or failed and the baseline is discarded. The set observed 2026-07-30 was
`{144, 147, 148, 149, 150}`, with 144 at `oauth_state.py:104`. If the set contains no entry for
`$FILE` on a complete read, this feature's premise is gone: stop and record that, rather than
"fixing" a finding that is not there.

```bash
# Alert 144's pre-change record, for the eventual before/after comparison.
# Single-alert endpoint, so no pagination applies.
gh api "repos/$REPO/code-scanning/alerts/144" \
  --jq '{number, state, fixed_at, dismissed_reason,
         path: .most_recent_instance.location.path,
         start_line: .most_recent_instance.location.start_line,
         commit_sha: .most_recent_instance.commit_sha,
         code_flows: (.most_recent_instance.code_flows | length)}'
```

`code_flows` is expected to be `0`. That is why no claim is made anywhere about the taint path.

```bash
# Unit suite baseline: expect 30 passed.
pytest tests/unit/auth/ -q
```

**How to read a baseline that is not 5.** Record the set, do not stop on the count. Three sibling
features are landing in this same window and each of them legitimately moves this number:
`001-ingestion-arn-logging` closes 148 through 150, `001-bad-tag-filter-dead-suppression` closes
147, and `001-codeql-coverage` enables an additional analysis leg that is *expected to raise* the
count (its own spec says so, and its SC-004 refuses to fail on a rise). Per the owner's directive,
coverage is the goal, not a low alert count.

What actually triggers `BLOCKED-REGRESSION` is narrow and attributable, per SC-003:

- the unit suite is not green, **or**
- a new open alert of any rule appears on `src/lambdas/shared/auth/oauth_state.py` or on
  `src/lambdas/shared/secrets.py`.

A repo-wide count moving for a sibling's reasons is recorded in the artifacts and is not a
regression. The gate is still not evaluated on a tree whose unit suite was already broken.

---

## Step 0b. Probe the dismissal permission, read-only, before anything can mutate an alert

Required by `specs/001-ingestion-arn-logging/codeql-logging-convention.md` **§5b**, consumed via
FR-008: "Check the permission with a read-only probe. **Never establish it by attempting a
dismissal**", because a successful dismissal cannot be cleanly reverted. This step exists so that
Step 4b is never used as a probe. It runs here, before the change is even applied, so the outcome is
known long before it is needed.

```bash
gh auth status 2>&1 | grep -i 'Token scopes'
PERM=$(gh api "repos/$REPO" --jq '{visibility, permissions}')
RC=$?; printf 'gh exit=%s\nperm=%s\n' "$RC" "$PERM"
```

Require `gh exit=0` and a non-empty `$PERM`, then record one of two outcomes:

- **available**: `visibility` is `public`, `permissions.push` is `true`, and the scope list contains
  `repo`. The update-code-scanning-alert endpoint needs `security_events` only on **private**
  repositories; on a public one `public_repo` suffices and `repo` subsumes it.
- **absent**: anything else. Step 4b is then not attempted at all, and the dismissal branch, if it is
  ever reached, terminates directly in `BLOCKED-ON-OWNER` (Step 4c).

**A missing `security_events` scope is not by itself a blocker.** Reading `gh auth status` alone and
concluding "no `security_events`, therefore blocked" is the specific mistake §5b exists to prevent,
and the sibling made it once before correcting it. Probed 2026-07-30 on this machine: scopes
`gist, read:org, repo, workflow`, `visibility: public`, `permissions.admin: true`, so the outcome is
**available** and `BLOCKED-ON-OWNER` is not the expected ending here.

---

## Step 1. Apply the change

Two files. Nothing else is opened. In particular `src/lambdas/shared/secrets.py` and
`src/lambdas/ingestion/handler.py` stay closed.

### 1a. `src/lambdas/shared/auth/oauth_state.py`

In `store_oauth_state()` only, delete the `safe_provider` assignment (lines 99-101) and the
`"provider"` entry from the `extra` dict, and add the documentation comment. The comment is
**required by FR-013**, on every branch of the gate including the confirmed one, and is not
optional polish:

```python
    # py/clear-text-logging-sensitive-data: no value derived from `provider` may
    # appear in this extra context. Removing the derived value, rather than
    # sanitizing it in place, is the shape that closed this rule in ebcc2f4.
    # See specs/001-oauth-provider-taint/research.md before adding a key here.
    logger.info(
        "OAuth state stored",
        extra={
            "has_user_id": user_id is not None,
            "ttl_seconds": OAUTH_STATE_TTL_SECONDS,
        },
    )
```

The `safe_provider` assignment must be **deleted**, not left orphaned: `ruff` selects `F` in
`pyproject.toml`, so an unused local fails `ruff check` with `F841 Local variable safe_provider is
assigned to but never used` at line 99, and the `Lint` job runs `ruff check src/ tests/`
(`.github/workflows/pr-checks.yml:62`), which is one of the four required contexts. Verified by
running it during Stage 4 clarification, not merely asserted. Leaving the derivation alive beside
the sink is also the exact shape `8424cbd` left behind, and FR-001 forbids it independently of what
the linter does.

`validate_oauth_state()` (its `safe_provider_validated` at line 253 and `extra` at line 258) is
**not** modified. FR-004.

### 1b. `tests/unit/auth/test_oauth_state.py`

Add `import logging` to the imports, and one method to `TestStoreOAuthState`:

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

No existing assertion is edited. FR-011, SC-004.

### 1c. Local gates

```bash
ruff format src/lambdas/shared/auth/oauth_state.py tests/unit/auth/test_oauth_state.py
ruff check src/lambdas/shared/auth/oauth_state.py tests/unit/auth/test_oauth_state.py
pytest tests/unit/auth/ -q          # expect 31 passed
make sast                            # bandit + semgrep
```

**`make validate` does not pass on this tree, and not because of this change.** It chains
`check-banned-terms`, which exits 1 today on 17 pre-existing matches of two legacy framework names in
other features' spec directories, including the raw plan-template placeholder left unfilled at
`specs/1268-cors-404-headers/plan.md:21`. The names are not repeated here, because writing them into
this directory is what the scanner exists to prevent; run the script to see them. Verified by
running it. Run the targeted gates above
instead, and if `make validate` is run anyway, confirm the only failures are those pre-existing
banned-term matches and that none of them is in `specs/001-oauth-provider-taint/` (verified clean).
Do not "fix" other features' directories to make the gate green; that is a separate feature's scope
and three sibling agents share this worktree. Carded, not folded in.

### SC-007 check, before the commit

The FR-013 comment is a spec requirement with its own success criterion, so verify it mechanically
rather than trusting the diff:

```bash
grep -n -B6 'OAuth state stored' src/lambdas/shared/auth/oauth_state.py
```

The window must be at least `-B5` and is set to `-B6` for one line of slack. `grep` matches the
string literal `"OAuth state stored",`, which sits below `logger.info(`, which sits below the four
comment lines, so the rule id is exactly five lines above the match. `-B4` prints a window that
excludes it and the check can never pass on correct code (Adversarial Review #3, finding **G-01**;
measured, `-B4` yields zero occurrences of the rule id and `-B5` yields one).

Expect the rule id `py/clear-text-logging-sensitive-data` present in the preceding comment block, and
expect **no** `# nosec`, `# noqa`, `# lgtm` or CodeQL pragma on any of those lines. Re-run this same
check against the merged file at the end of Step 4a or 4b: SC-007 is stated against the merged file,
and it is the one criterion that is true on the `CONFIRMED` branch as well as the refuted one.

FR-003 sanity check, by inspection of the diff: the `put_item` item dict, the returned `OAuthState`,
and the `code_verifier` generation are untouched. The diff touches only the two lines described
above plus the comment.

### 1d. If the change cannot land: terminal state `PENDING-BRANCH-ANALYSIS`

Read this before Step 2, because for this feature it is the likeliest ending rather than an edge
case, and the convention says so in those words.

Closure is read from a default-branch analysis (FR-009, and convention §3 Trap 3), so **no
qualifying analysis can exist while the change sits on a feature branch**. If the push or the merge
is gated on the repository owner, or the PR is open and unmerged, stop here and record terminal state
**`PENDING-BRANCH-ANALYSIS`**, inherited from
`specs/001-ingestion-arn-logging/codeql-logging-convention.md` **§5a** via FR-008. Record that the
code change and its regression guard are complete and green, and write the Step 3a gate query,
filled in with this feature's `$RULE` and `$FILE`, into this directory so the check is mechanical the
moment the change lands. Report it as **neither done nor failed**, and do not evaluate the gate.

This is **not** `BLOCKED-NO-ANALYSIS`. That state's 7-day clock starts only once the change is on
`main` (Step 2). This one is entered before the change gets there, and the clock has not started.

Commit GPG-signed on the feature branch, open a PR, merge through the normal pipeline. Record the
resulting **merge commit SHA on `main`**:

```bash
export CHANGE_SHA=<merge commit sha on main>
```

---

## Step 2. Wait for a default-branch analysis that contains the change

The `codeql` job (name `Analyze`, category `/language:python`) lives in
`.github/workflows/pr-checks.yml` and triggers on `push` to `main`. Recent default-branch analyses
have landed within roughly 25 minutes of their commit.

```bash
gh api "repos/$REPO/code-scanning/analyses?ref=refs/heads/main&per_page=5" \
  --jq '.[] | {id, commit_sha, created_at, analysis_key, category}'
export ANALYZED_SHA=<commit_sha of the newest analysis>
```

### Freshness proof (mandatory, do not skip)

A result predating the change decides nothing. Prove the change is in the analyzed tree:

```bash
gh api "repos/$REPO/compare/$CHANGE_SHA...$ANALYZED_SHA" --jq '.status'
```

Accept only `ahead` or `identical`. `behind` or `diverged` means the analysis does not cover the
change; discard the observation and keep waiting.

**Bound**: if no analysis satisfying this check exists **7 days** after `CHANGE_SHA` landed on
`main`, stop. Terminal state `BLOCKED-NO-ANALYSIS`: report to the repository owner naming the missing
analysis. Do not classify. Do not dismiss. This is a terminal reportable state, not a third attempt.

---

## Step 3. Read the gate

### 3a. Open findings for this rule at this path, on the default branch

Two rules govern this query, and the second is why the first is not enough.

`gh api` has **no `--arg` flag** (its only jq flag is `--jq`/`-q`, which takes one expression). Do
not pipe `gh api` into a standalone `jq` to get one either: a failed `gh api` piped into `jq` yields
empty output, which is indistinguishable from the pass condition and would be misread as
`Confirmed`. If you ever do pipe, check `PIPESTATUS[0]`. The shape below avoids the whole question by
writing the response to a file and running `jq` over the file, where `jq --arg` is available and
where nothing sits downstream of a pipe.

And the read **must be paginated**, per "Read this before running any alerts query" at the top of this
runbook: unpaginated, this exact query
reports zero open alerts on a repository that has five, and exits 0 while doing it.

#### The control, first. It is not optional.

The gate's pass condition is empty output, so it is worthless without proof that the query can return
anything at all. A typo in `$RULE`, `$FILE` or the ref returns `[]` forever and reads as success.
The control is the same corpus, same filters, with the `state == "open"` predicate dropped.

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

Require all four, each a figure measured 2026-07-30 rather than a vague "non-empty": `gh exit=0` and
`jq exit=0`; `corpus` at least **137**; `rule_total` at least **22**; and `$CTRL` containing **alert
117**, which is `state: fixed` at this path for this rule and is therefore an immovable anchor, so
the control stays satisfied after the change lands whatever the outcome. Measured `$CTRL`:
`[{"number":144,"state":"open"},{"number":117,"state":"fixed"}]`. Alert 117 is a fixture for the
control here, never a criterion for the gate.

If any of the four fails, the read or the query shape is broken and **the gate result below is not an
observation**. Discard it and re-run.

#### The gate itself

Filters the same file the control just validated. Do not re-fetch in between.

```bash
GATE=$(jq -c --arg r "$RULE" --arg f "$FILE" \
  '[.[][] | select(.state == "open")
          | select(.rule.id == $r)
          | select(.most_recent_instance.location.path == $f)
          | {number, start_line: .most_recent_instance.location.start_line,
             commit_sha: .most_recent_instance.commit_sha}]' "$ALERTS_JSON")
JQ_RC=$?; printf 'jq exit=%s\ngate=%s\n' "$JQ_RC" "$GATE"
```

An empty array `[]` is the pass condition **only if** the control passed on all four floors and
`jq exit=0`. A blank `$GATE` is a failed filter, not a closed alert, and the observation is discarded
rather than classified.

Per FR-009, this is the only admissible evidence. A green `Analyze` check on a pull request is not:
CodeQL is not a required status check here, and a PR run reports into the PR's own ref.

An empty array under those conditions is **Confirmed**, full stop. The criterion is path plus rule
id, and that is the strongest identity the API supports: `most_recent_instance.location` carries
`path`, `start_line`, `end_line`, `start_column` and `end_column`, and no function field.

### 3b. Only if the result is non-empty: attribute each survivor at the analyzed commit

This step never turns a non-empty result into a pass. It decides **who owns the survivor**, nothing
else. The mapping is derived from a `start_line`, so it inherits the line instability the gate is
built to avoid, which is exactly why it is not the criterion. Never map against the working tree, and
never against a line window frozen at authoring time.

```bash
gh api "repos/$REPO/contents/$FILE?ref=$ANALYZED_SHA" --jq '.content' \
  | base64 -d | grep -n '^def '
```

`store_oauth_state()` spans from its `def` line to the line before the next top-level `def`. A
finding whose `start_line` falls in that span is this feature's to dismiss. One outside it is a
different function, most likely the FR-004-frozen `validate_oauth_state()` sink at lines 253 to 258,
which carries the same sanitize-in-place shape and is not this feature's to touch. That case is
**reported, never dismissed here, and never scored as Confirmed**.

Check `PIPESTATUS[0]` on the fetch above. A failed `gh api` piped into `base64 -d` produces no
matches, which reads as "no functions found" rather than as an error.

### 3c. Classify, once

| Observation | Classification | Action |
|---|---|---|
| Step 3a returns empty **and** `gh exit=0` | **Confirmed** | Go to Step 4a. Stop. No dismissal. |
| Alert 144 still open on the path, attributed to `store_oauth_state()` | **Refuted** | Go to Step 4b, dismissing 144. |
| 144 closed but a different alert number for this rule is open on the path, attributed to `store_oauth_state()` | **Refuted** (a respawn, exactly what `8424cbd` produced) | Go to Step 4b, dismissing the new number, and record that a respawn occurred. |
| A finding for this rule is open on the path but attributes outside `store_oauth_state()` | **Not Confirmed**, and not this feature's | Terminal state `REPORTED-FOREIGN-SINK`. Report to the owner per FR-006a with the alert number, `start_line` and `ANALYZED_SHA`. Do not dismiss. Do not edit `validate_oauth_state()` (FR-004). |
| Step 3a errored (`gh exit` non-zero) | Not an observation | Discard and re-run. Empty output from a failed call is not a pass. |
| No fresh analysis (Step 2's freshness proof never satisfied) | Not yet decidable | Wait, bounded at 7 days, then `BLOCKED-NO-ANALYSIS`. |

The change is retained on the refuted branch as well. It is a defensible improvement on its own
terms, and reverting it would restore a derived-string log for no benefit.

---

## Step 4a. Terminal state `CONFIRMED`

```bash
gh api "repos/$REPO/code-scanning/alerts/144" \
  --jq '{number, state, fixed_at, dismissed_reason}'
```

Record in this feature's artifacts: the analysis `id` and `commit_sha`, the `compare` status that
proved freshness, alert 144's `fixed_at` as **corroboration only** (expected non-null and dated at or
after `CHANGE_SHA`; the pass was already decided by Step 3a's empty result, and 144 is a locating
label, not the criterion), and
the SC-003 recount below. Then stop. No dismissal, no tech debt entry.

```bash
# SC-003 is an attribution check, not a count. List the open set with paths and
# compare it to the Step 0a baseline set, then confirm the binding condition:
# no new alert of any rule on oauth_state.py or on secrets.py.
export AFTER_JSON=/tmp/oauth-alerts-after.json
gh api --paginate --slurp \
  "repos/$REPO/code-scanning/alerts?ref=refs/heads/main&per_page=100" > "$AFTER_JSON"
GH_RC=$?
CORPUS=$(jq '[.[][]] | length' "$AFTER_JSON"); JQ_RC=$?
AFTER=$(jq -c '[.[][] | select(.state == "open")
                      | {number, rule: .rule.id,
                         path: .most_recent_instance.location.path}]' "$AFTER_JSON")
printf 'gh exit=%s jq exit=%s corpus=%s\nafter=%s\n' "$GH_RC" "$JQ_RC" "$CORPUS" "$AFTER"
```

Require `gh exit=0`, `jq exit=0` and `corpus` at least **137** before believing the comparison.
Unpaginated, this query reads zero open alerts and would certify SC-003 while blind.

Record the diff against the Step 0a set and name which sibling feature each change belongs to. A
higher total that is wholly attributable to `001-codeql-coverage`'s new analysis leg satisfies
SC-003; it does not breach it. Also re-run the SC-007 comment check from Step 1c against the merged
file.

Note on reading the result: `state` alone is not proof of repair. Dismissal is sticky and survives a
later genuine fix, which is why alerts 26 and 27 read `dismissed` while carrying `fixed_at`, and why
alerts 22 through 25 read `dismissed` with `fixed_at` still null eight months on. `fixed_at` is the
load-bearing field.

---

## Step 4b. Terminal state `REFUTED-DISMISSED`

Only reachable after the Step 1 change has landed and been refuted at the gate (FR-007), **and** only
if Step 0b's read-only probe recorded the outcome **available**. If it recorded **absent**, do not
run the `PATCH` below at all: go straight to Step 4c. The `PATCH` here is the intended dismissal, not
a permission probe, and it is only ever reached with the permission question already answered.

The justification carries the three elements settled at
`specs/001-ingestion-arn-logging/codeql-logging-convention.md` **§2**, consumed here rather than
redefined (FR-008). Cite the convention's section, not a sibling requirement number: FR-008 requires
restatements to anchor on that document so a renumbering in the sibling cannot silently break this
feature. Adjust `<N>` and the alert-number references to what was actually observed.

```bash
export ALERT=<observed alert number>
export JUSTIFICATION="Not a credential. The only non-constant input to this expression was the \
OAuth provider name, a two-value identifier ('google' or 'github') passed as a string literal by \
both production call sites, and it has now been removed from the log context entirely, so no value \
derived from it reaches this sink at all. Convention applied: the no-derived-value-in-log-context \
shape established by ebcc2f4 (PR #322) and recorded in specs/001-ingestion-arn-logging; see \
specs/001-oauth-provider-taint/research.md. Why CodeQL still reports the flow: unknown. The alert \
returns zero code_flows, so the taint path cannot be inspected, and the finding survives the exact \
rewrite that carries a non-null fixed_at on alerts 26, 27, 106, 107, 110 and 111. The value is \
persisted deliberately in the DynamoDB item written at oauth_state.py:87 and is unaffected."

gh api -X PATCH "repos/$REPO/code-scanning/alerts/$ALERT" \
  -f state=dismissed \
  -f dismissed_reason='false positive' \
  -f dismissed_comment="$JUSTIFICATION"

# Verify it took.
gh api "repos/$REPO/code-scanning/alerts/$ALERT" \
  --jq '{number, state, dismissed_reason, dismissed_comment, dismissed_at, dismissed_by: .dismissed_by.login}'
```

Then add a tech-debt card, per **FR-007** (a dismissal is a documented security shortcut).
**Re-targeted 2026-07-31**: this step wrote an entry to `docs/reference/TECH_DEBT_REGISTRY.md`;
`001-constitution-prune` deleted that file and the constitution section mandating it. Add a card to
the `CARDS` array in **`CLEANUP-BOARD.html`** instead, with `lane: "track"`, a `title` naming
`store_oauth_state()`, `evidence` carrying the alert number and the exact dismissal justification,
`citation` `src/lambdas/shared/auth/oauth_state.py`, a `next_action`, and `source` naming this
directory. No identifier is allocated: cards have no id field, which retires the merge-time
collision hazard this step used to guard against.

Finally, recount for SC-003 as in Step 4a.

---

## Step 4c. Terminal state `BLOCKED-ON-OWNER`

Reached when **Step 0b's read-only probe recorded `absent`**, which is how the permission question is
answered here. Inherited via FR-008 from
`specs/001-ingestion-arn-logging/codeql-logging-convention.md` **§5b**, not newly defined here. The
three bullets below are a restatement for convenience; §5b governs if they ever drift.

A Step 4b `PATCH` that fails on permissions despite a probe reading `available` also lands here, but
that is a contradiction to record and investigate, not the normal route in. The route in is the
probe. §5b is unconditional that permission is never established by attempting a dismissal, because a
successful one cannot be cleanly reverted, and this runbook previously had no probe at all, which
left the failed `PATCH` doing that job by default.

Write a handoff artifact into `specs/001-oauth-provider-taint/` carrying:

- the exact alert numbers observed on the path and attributed to `store_oauth_state()`, with their
  `start_line` and the
  `ANALYZED_SHA` they were read from;
- the exact `JUSTIFICATION` text above, verbatim, per alert;
- the exact `gh api -X PATCH` invocation, ready to run.

State plainly that the code change is independently complete and mergeable and only the dismissal is
outstanding. A feature blocked this way is reported as neither done nor failed.

---

## Step 5. Anti-checklist

None of these may be done at any point, on any branch:

- Suppressing the rule repo-wide, lowering its severity, excluding the file from analysis, or adding
  an inline suppression comment as a substitute for the dismissal (FR-010). The comment added in
  Step 1a is documentation, is required by FR-013, and carries no `# nosec`, `# noqa`, `# lgtm` or
  CodeQL pragma. FR-010 and FR-013 do not conflict: one forbids suppressing the finding, the other
  requires explaining it.
- Skipping the Step 1a comment because the gate came back `CONFIRMED`. FR-013 is unconditional. The
  refactor that would reintroduce the key is written against the source file, not against `specs/`.
- Substituting a literal, an allowlist-selected constant, or any other stand-in for the removed
  `provider` value (FR-002). Deleted for cause by Adversarial Review #1.
- Editing `validate_oauth_state()` (FR-004).
- Editing `src/lambdas/shared/secrets.py`. Its alerts 22 through 25 are live findings behind sticky
  dismissals with `fixed_at` null; touching those lines re-fingerprints them into fresh open alerts,
  which is what happened to that file on 2025-12-09.
- Editing `src/lambdas/ingestion/handler.py` or its alerts 148 through 150. Sibling feature
  `001-ingestion-arn-logging` owns them.
- Citing a pull request check result as evidence of closure (FR-009).
- Reporting `CONFIRMED` because alert 144 disappeared, without checking whether a replacement number
  for this rule appeared anywhere on the path. That is precisely what `8424cbd` produced: it closed
  alert 117 at line 95 and opened alert 144 at line 104 in the same run. The criterion is path plus
  rule id, never the function and never one alert number.
- Reading a code-scanning alerts query without `--paginate`, or believing one whose corpus floor was
  not checked. Unpaginated, the open set reads as empty on a repository with five open alerts, and
  the call exits 0. Emptiness is the pass condition here, so a truncated read certifies the gate while
  blind. `per_page=100` alone does not fix it.
- Establishing the dismissal permission by attempting a dismissal (convention §5b). Step 0b probes it
  read-only, before the change is even applied. A successful dismissal cannot be cleanly reverted.
- Revisiting the seven existing dismissals of this rule, or changing analysis configuration, query
  packs, or scan scheduling.
