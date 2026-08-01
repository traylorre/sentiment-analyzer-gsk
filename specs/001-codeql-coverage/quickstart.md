# Quickstart: CodeQL Coverage Expansion

Operator runbook for the sequence in [plan.md](./plan.md). Commands are read-only unless marked
MUTATES. Every mutation stays on `001-codeql-coverage` until Phase D.

**Repo**: `traylorre/sentiment-analyzer-gsk`. Set once:

```bash
export REPO=traylorre/sentiment-analyzer-gsk
export BR=001-codeql-coverage
export WF=pr-checks.yml
```

## Reference cheat sheet

| Reference | Proves | Barred from |
|---|---|---|
| `refs/pull/*/merge` | Nothing about coverage. Diff-informed, routinely 0 results. | All coverage evidence (FR-018) |
| `refs/heads/001-codeql-coverage` | Pre-merge only: the leg runs, both dashboards extract, wall clock is bounded (SC-002, SC-003, SC-007) | Baseline capture (FR-019) |
| `refs/heads/main` | The authoritative baseline; starts the A1 clock (SC-001, SC-004, SC-005) | Nothing |

## Phase A. Pre-flight

```bash
# A0, BEFORE A1. Get onto the branch, then prove the branch exists on origin.
# `gh workflow run --ref` resolves the ref SERVER-SIDE, so a branch that exists only locally
# makes A1 fail for a reason that has nothing to do with dispatch permission, which is exactly
# the misreading FR-009c would then record. This gate is what tells the two apart.
git rev-parse --verify "$BR" >/dev/null 2>&1 && git switch "$BR" || git switch -c "$BR"
git rev-parse --abbrev-ref HEAD                  # must print 001-codeql-coverage

git ls-files specs/001-codeql-coverage/ | wc -l   # must be > 0 before anything is pushed
git ls-remote --exit-code --heads origin "$BR"; echo "ls-remote rc=$?"
# rc=0 means the ref exists and A1 below is a real permission test.
# rc=2 means the ref does NOT exist. Do NOT dispatch: push the branch first. Recording A1 as
# NOT RUNNABLE on the strength of a dispatch failure taken while the ref did not exist is the
# one wrong answer here.
```

```bash
# A1: can we dispatch on the feature branch at all? Only meaningful once ls-remote rc=0.
gh workflow run "$WF" --repo "$REPO" --ref "$BR"; echo "dispatch rc=$?"
sleep 15
gh run list --repo "$REPO" --workflow "$WF" --branch "$BR" --limit 3 \
  --json databaseId,event,status,createdAt --jq '.[]'
```

```bash
# A2: snapshot the 5 open Python alerts BEFORE anything changes. SC-005 forbids any of them
# DISAPPEARING as a side effect of the config work, and that is only checkable against a
# pre-change list. Identity is the (rule, path) PAIR, never the alert number: closing an alert
# and rewriting the line spawns a fresh number at the same location, so a number-keyed diff
# reports a loss that did not happen. Numbers are kept only as a lookup convenience.
#
# --paginate WITHOUT --slurp applies --jq once PER PAGE, so an AGGREGATING filter emits one
# object per page instead of one for the whole set. Redirect to a file, then jq the file.
gh api "repos/$REPO/code-scanning/alerts?ref=refs/heads/main&state=open&per_page=100" \
  --paginate --slurp > /tmp/a2-raw.json
rc=$?
[ "$rc" -eq 0 ] && [ -s /tmp/a2-raw.json ] \
  || { echo "A2 API READ FAILED (rc=$rc). An empty list would read as a clean repository. STOP."; exit 1; }
jq '[.[][] | {key: "\(.rule.id)@\(.most_recent_instance.location.path)",
              number, sev: .rule.security_severity_level}] | sort_by(.key)' \
  /tmp/a2-raw.json | tee /tmp/a2-prechange.json | jq 'length'
```

Failure at A1 is not a blocker, it is an outcome, and after Q4 it is a small one: B1 needs no
dispatch, so only the OPTIONAL B2 arm is lost. Record it NOT RUNNABLE under FR-009c, retain the
query filter unchanged per FR-009b, keep B1 and B3, and take all User Story 1 evidence from
`refs/heads/main` after merge.

**A3: route the two Clarification DEFERRALS.** Neither has a home outside spec.md's Clarifications
appendix, which is where deferrals expire.

**Deferral 2, the 10-working-day window (Q5), is a STEP, not a note. Do it here.** FR-021 writes
the computed close-out date into the baseline record at capture time and FR-016a allows exactly ONE
extension, so an answer arriving after E2 spends that single extension on an authoring correction
instead of on alert volume.

1. Ask the owner, **now**, at Phase A: confirm 10 working days, or name a different number.
   Owner: Admin Role (Project Owner: @traylorre), `CONTRIBUTING.md:64`.
2. Write ONE of these two literal strings into the evidence log's baseline record. **A blank field
   fails this step**, and so does anything that is neither of these two:
   - `WINDOW: 10 working days, CONFIRMED by owner on YYYY-MM-DD`
   - `WINDOW: 10 working days, ASSUMED, Deferral 2 unanswered at capture`
3. If it is still unanswered when E2 runs, take the ASSUMED string. Do not block on it and do not
   invent an answer. Treat any later owner change as the FR-016a extension it is, spending the
   single permitted extension on an authoring correction. That is the cost this step exists to
   avoid, and it is a cost, not a failure.

- **Deferral 1, the stale constitution §9 path (Q2). Not blocking.** Carried into the F2
  enforcement recommendation so it reaches the same named decider under the same decision-by date.
  Record `DEFERRAL 1: routed to enforcement-recommendation.md (F2), not blocking` in the evidence
  log, and confirm the recommendation's checklist carries the question verbatim.

Record both, with status, in the evidence log.

## Phase B. Config resolution (Python-only, matrix untouched)

**AMENDED at Clarification Q4. Do NOT run the three-arm probe.** FR-009b now forbids arms 1 and 2
because they are already ANSWERED, and running them would mutate the shared config to re-derive a
settled fact. One arm survives and it is OPTIONAL.

| Arm | `paths-ignore: tests/**/*` | `query-filters` py rule | Status |
|---|---|---|---|
| 1 (today) | retained | retained | **ANSWERED at Q4, MUST NOT run** |
| 2 | REMOVED | retained | **ANSWERED at Q4, MUST NOT run** |
| 3 (control) | REMOVED | REMOVED | OPTIONAL, single-purpose: delete or retain the inert filter |

**B1, read-only**: transcribe the Q4 evidence into the probe record. No dispatch, no mutation.
This step alone satisfies SC-009 and SC-010.

```bash
# The finding, already on refs/heads/main. Re-read it rather than re-deriving it.
#
# GUARD FIRST. Several checks below have ZERO as their PASS value, so a failed fetch produces an
# empty file and every one of them renders as a pass. Assert the log is real before reading it.
gh run view 30581930915 --repo "$REPO" --log --job 91004036909 > /tmp/py-main.log
rc=$?
[ "$rc" -eq 0 ] && [ -s /tmp/py-main.log ] \
  || { echo "LOG FETCH FAILED (rc=$rc). Every zero below is meaningless. STOP."; exit 1; }
grep -c . /tmp/py-main.log                         # sanity: total log lines, must be large

grep -n 'filter exclude' /tmp/py-main.log          # extractor invoked with --filter exclude:tests/**/*
grep -c 'Extracted file' /tmp/py-main.log          # expect 152. If 0, the guard above failed.
grep 'Extracted file' /tmp/py-main.log | grep -c '/tests/'; echo "first-grep rc=${PIPESTATUS[0]}"
# ^ expect 0, and first-grep rc must be 0 too. A 0 count with first-grep rc=1 means the first
#   grep matched nothing, ie. the log is wrong or empty, NOT that no test file was extracted.
grep -n 'CodeQL scanned' /tmp/py-main.log          # "152 out of 154 Python files", line 2067
git ls-files '*.py' | grep -c '^tests/'            # expect 393, none of which are in the database
```

**B2, OPTIONAL, MUTATES**: run the control arm ONLY to decide whether to DELETE the inert query
filter as dead or RETAIN it against a future narrowing of the path exclusion.

```bash
# MUTATES: remove BOTH paths-ignore: tests/**/* and the py/... query filter, then
git commit -S -am "probe(001): codeql config control arm"
git push origin "$BR"
gh workflow run "$WF" --repo "$REPO" --ref "$BR"

gh api "repos/$REPO/code-scanning/analyses?ref=refs/heads/$BR&per_page=100" \
  --paginate --slurp > /tmp/b2-analyses.json
rc=$?
[ "$rc" -eq 0 ] && [ -s /tmp/b2-analyses.json ] \
  || { echo "ANALYSES READ FAILED (rc=$rc). An empty list is not 'the arm produced nothing'. STOP."; exit 1; }
jq '[.[][] | {id, category, created_at, results_count, commit_sha}] | sort_by(.created_at) | reverse' \
  /tmp/b2-analyses.json

# Results MUST come from that analysis's SARIF, not from the alerts endpoint. An alert carries
# only `most_recent_instance`, which a later run on the same ref overwrites, so an alerts query
# reports the newest run twice and cannot separate two runs of one reference.
ID=<analysis id for this arm, matched by commit_sha to the probe commit>
gh api "repos/$REPO/code-scanning/analyses/$ID" \
  -H "Accept: application/sarif+json" > "/tmp/arm-$ID.sarif"
rc=$?
[ "$rc" -eq 0 ] && [ -s "/tmp/arm-$ID.sarif" ] \
  || { echo "SARIF FETCH FAILED (rc=$rc). A zero result below would be a read failure. STOP."; exit 1; }
jq '[.runs[].results[] | .locations[0].physicalLocation.artifactLocation.uri as $p
     | select($p | startswith("tests/"))
     | {rule: .ruleId, path: $p}]
    | {count: length, rules: [.[].rule] | unique, paths: [.[].path] | unique}' \
  "/tmp/arm-$ID.sarif"
```

**B2 outcome**: zero results under `tests/`, or the arm not run at all, both resolve the SAME way
under FR-009b. The query filter is **RETAINED unchanged**, because deleting a rule without
evidence is what FR-008 forbids. The rule may simply no longer fire (F4: six of eight historical
alerts are `fixed`). Neither outcome blocks the feature and neither fails SC-009 or SC-010.

**B3, MUTATES**: revert anything B2 changed, then apply the FR-011 resolution. Q4 already settled
the wording half in every case: delete the claim at `.github/codeql/codeql-config.yml:13` that
"All other security rules apply to tests", which is FALSE, and make the real intent explicit. No
rule is added or removed except on the strength of a B2 result. FR-012 binds the edit: Python
coverage must not drop below the F7 baseline for any rule but the deliberately filtered one.

## Phase C. Matrix change

```yaml
# MUTATES .github/workflows/pr-checks.yml, job `codeql` (name: Analyze)
    strategy:
      fail-fast: false
      matrix:
        language: ['python', 'javascript-typescript']
```

Add the FR-022 warning comment from plan.md D-7 to the job header. Then:

```bash
git commit -S -am "feat(001): add javascript-typescript to the CodeQL matrix"
git push origin "$BR"
gh workflow run "$WF" --repo "$REPO" --ref "$BR"

# SC-002: the leg reports a results count.
# --paginate is load-bearing, not cosmetic: this branch accumulates one analysis per language per
# dispatch, and a default 30-item page truncates newest-first. An unpaginated read can return a
# page holding no JavaScript/TypeScript entry at all, and a truncated read must NEVER be recorded
# as an SC-002 failure. Any results_count value including 0 passes; an ABSENT analysis does not.
gh api "repos/$REPO/code-scanning/analyses?ref=refs/heads/$BR&per_page=100" \
  --paginate --slurp > /tmp/c2-analyses.json
rc=$?
[ "$rc" -eq 0 ] && [ -s /tmp/c2-analyses.json ] \
  || { echo "ANALYSES READ FAILED (rc=$rc). An absent entry below would be a read failure. STOP."; exit 1; }
jq '{total: ([.[][]] | length),
     jsts: [.[][] | select(.category != null and (.category | test("javascript")))
            | {id, category, created_at, results_count}]}' /tmp/c2-analyses.json

# SC-003 + FR-004a: both dashboards extracted, and any resolution warnings
RUN=$(gh run list --repo "$REPO" --workflow "$WF" --branch "$BR" --limit 1 --json databaseId --jq '.[0].databaseId')
echo "RUN=$RUN"; [ -n "$RUN" ] || { echo "RUN EMPTY. STOP."; exit 1; }
JOB=$(gh run view "$RUN" --repo "$REPO" --json jobs \
  --jq '.jobs[] | select(.name=="Analyze (javascript-typescript)") | .databaseId')
echo "JOB=$JOB"; [ -n "$JOB" ] || { echo "JOB ID EMPTY. STOP."; exit 1; }
gh run view "$RUN" --repo "$REPO" --log --job "$JOB" > /tmp/jsleg.log
rc=$?
# GUARD. The FR-004a check below treats EMPTY as good news ("no resolution warnings"), so a failed
# fetch would report a clean bill of health. Assert the log exists before believing any silence.
[ "$rc" -eq 0 ] && [ -s /tmp/jsleg.log ] \
  || { echo "JS LEG LOG FETCH FAILED (rc=$rc). Silence below is a read failure, not a result. STOP."; exit 1; }
wc -l /tmp/jsleg.log

# TIER 1 (primary). Paths in these lines are ABSOLUTE runner paths appearing MID-LINE, after the
# "<job>\t<step>\t<timestamp>" prefix gh prepends. A line-anchored '^frontend/' returns 0
# UNCONDITIONALLY and is a guaranteed false negative. Match unanchored substrings.
grep 'Extracted file' /tmp/jsleg.log | grep -c '/frontend/';      echo "t1a first-grep rc=${PIPESTATUS[0]}"
grep 'Extracted file' /tmp/jsleg.log | grep -c '/src/dashboard/'; echo "t1b first-grep rc=${PIPESTATUS[0]}"
grep -c 'Extracted file' /tmp/jsleg.log            # per-file lines present at all? 0 routes to tier 2

# TIER 2 (only if tier 1 emitted NO per-file lines at all). Per-file logging is extractor-specific
# and the JavaScript extractor exposes no logging-verbosity option, so silence here means
# "the log did not say", never "the directory was not extracted".
grep -E 'Calling |extractor|--filter' /tmp/jsleg.log | head -20

# TIER 3 (corroboration only; tolerance is wider than src/dashboard's 6 files)
grep 'CodeQL scanned' /tmp/jsleg.log
git ls-files '*.js' '*.jsx' '*.ts' '*.tsx' '*.mjs' '*.cjs' | grep -vcE '^tests/'   # expect 290

# FR-004a. EMPTY here means "no resolution warnings", which is the good outcome, so it is only
# believable if the guard above passed. Record which it was, never just "none found".
grep -inE 'could not resolve|module resolution|type resolution|no such module|cannot find module' /tmp/jsleg.log
echo "grep rc=$? (0 = warnings found, 1 = genuinely no warnings, 2 = file unreadable)"

# SC-007: leg duration and workflow total. GUARD FIRST, then assert the leg is present at all:
# a missing leg in this read is a read failure, not a fast leg.
gh run view "$RUN" --repo "$REPO" --json jobs > /tmp/c2-jobs.json
rc=$?
[ "$rc" -eq 0 ] && [ -s /tmp/c2-jobs.json ] \
  || { echo "JOBS READ FAILED (rc=$rc). A missing leg below is a read failure. STOP."; exit 1; }
jq '.jobs[] | {name, started_at, completed_at}' /tmp/c2-jobs.json
jq '[.jobs[] | select(.name | test("javascript-typescript"))] | length' /tmp/c2-jobs.json  # must be 1
gh run view "$RUN" --repo "$REPO" --json createdAt,updatedAt,conclusion --jq '.'
```

Record the analysis id from this step in the evidence log **as excluded from baseline capture**.

## Phase D. Merge, then discharge the §9 obligation

The feature stays OPEN after merge (FR-023). Before moving on, write the two UNCONDITIONAL tech
debt entries the Q2 triage identified. The Constitution Check in plan.md records §9 as PASS **with
obligation**; skipping this makes that row false.

```bash
# Allocate identifiers AT WRITE TIME against the registry's then-highest value. Never pre-reserve:
# TD-024 is contested by sibling features, and pre-reserving is what created that collision.
#
# RE-TAKE THIS READ IMMEDIATELY BEFORE YOU WRITE, not once at the top of the phase. A sibling
# feature merging in between moves the highest value, and a value read minutes ago is already a
# guess. If you write two entries, re-read between them is unnecessary but re-reading before the
# FIRST one is not optional.
grep -oE 'TD-[0-9]{3}' docs/reference/TECH_DEBT_REGISTRY.md | sort -u | tail -1
echo "rc=${PIPESTATUS[0]}"
```

Two registry entries, per constitution §9(a). §9(b)'s labelled issue is NOT raised: the owner has
directed that the `tech-debt` label not be created, so record that half as outstanding. Do not run
`gh label create` or `gh issue create`, and do not substitute another label.

1. npm ecosystem absent from `.github/dependabot.yml` while 82 npm advisories are open (F18).
2. The §10 local-SAST gap: `make sast` covers `src/` only, so after this lands CodeQL covers
   `frontend/` and no local pre-push tier does.

A third, conditional entry is owed only if the FR-016b lapse path fires at close-out.

## Phase E. Baseline (after merge only)

```bash
# E1: the FIRST refs/heads/main javascript-typescript analysis after merge.
# --paginate is what makes the sort mean anything: refs/heads/main carries ~948 analyses, and an
# unpaginated 30-item page read yields an oldest-of-PAGE, not an oldest. Measured, that is an
# eight-month error in the value that becomes a deadline.
gh api "repos/$REPO/code-scanning/analyses?ref=refs/heads/main&per_page=100" \
  --paginate --slurp > /tmp/e1-analyses.json
rc=$?
[ "$rc" -eq 0 ] && [ -s /tmp/e1-analyses.json ] || { echo "E1 READ FAILED (rc=$rc). STOP."; exit 1; }
# COUNT FLOOR FIRST. `sort_by | .[0] | {id, category}` over an EMPTY selection prints
# {"id":null,"category":null}, whose type is "object" and whose `. == null` is false. "A non-null
# object printed" is NOT the check; N > 0 is. Otherwise `null` gets written into the FR-021
# baseline record as the identifier that starts the triage clock.
N=$(jq '[.[][] | select(.category != null and (.category | test("javascript")))] | length' \
      /tmp/e1-analyses.json)
echo "jsts_analyses=$N"
[ "$N" -gt 0 ] \
  || { echo "ZERO javascript-typescript analyses on refs/heads/main. SC-001 NOT met. STOP."; exit 1; }
# .category is null-guarded before test(): `null | test(...)` aborts the whole filter rather than
# skipping a row. sort_by then .[0] takes the EARLIEST, which is what A1 requires; the API's
# default ordering is newest first, so dropping the sort starts the clock late.
jq '[.[][] | select(.category != null and (.category | test("javascript")))]
    | sort_by(.created_at) | .[0]
    | {id, category, created_at, results_count, commit_sha}' /tmp/e1-analyses.json

# E2: the baseline alert set. Filter to state=open so it is the SAME population A2 captured,
# otherwise the SC-004 "before 5 / after N" delta compares open-only against all-states and
# reports a large FICTITIOUS increase inside a feature whose central claim is that a real
# increase is expected. A fake increase inside that framing is uniquely hard to catch.
gh api "repos/$REPO/code-scanning/alerts?ref=refs/heads/main&state=open&per_page=100" \
  --paginate --slurp > /tmp/e2-raw.json
rc=$?
[ "$rc" -eq 0 ] && [ -s /tmp/e2-raw.json ] || { echo "E2 READ FAILED (rc=$rc). STOP."; exit 1; }
# The `other` bucket is deliberate, not decoration. The Python leg also analyzes GitHub Actions
# workflow files, so a two-bucket js/ + py/ partition is NOT exhaustive and would silently drop
# actions/-prefixed alerts from both the baseline and the delta. partition_check proves it.
jq '[.[][] | {number, rule: .rule.id, sev: .rule.security_severity_level,
              path: .most_recent_instance.location.path,
              key: "\(.rule.id)@\(.most_recent_instance.location.path)"}]
    | {total_open: length,
       jsts:   [.[] | select(.rule | startswith("js/"))],
       python: [.[] | select(.rule | startswith("py/"))],
       other:  [.[] | select((.rule | startswith("js/")) or (.rule | startswith("py/")) | not)]}
    | . + {partition_check: (.total_open == ((.jsts|length)+(.python|length)+(.other|length)))}' \
  /tmp/e2-raw.json | tee /tmp/e2-baseline.json \
  | jq '{total_open, jsts: (.jsts|length), python: (.python|length), other: (.other|length), partition_check}'

# E3 SC-005: Python floor of 9. A FLOOR, not an equality: if the config work widened Python scope
# the count rises above 9, and an equality test would fail the feature for producing exactly the
# outcome FR-012 protects.
jq '[.[][] | select(.category != null and (.category | test("python")))]
    | sort_by(.created_at) | reverse | .[0] | {id, created_at, results_count}' /tmp/e1-analyses.json

# E3 SC-006: exactly four required contexts, unchanged. Print BOTH .contexts (deprecated but still
# populated) and .checks[].context, plus both length floors. A null from a dropped or renamed API
# field would otherwise satisfy "no unexpected context" vacuously. This is a single object, not a
# paginated collection, so --paginate does not apply; the floors do.
gh api "repos/$REPO/branches/main/protection/required_status_checks" > /tmp/e3-protection.json
rc=$?
[ "$rc" -eq 0 ] && [ -s /tmp/e3-protection.json ] \
  || { echo "PROTECTION READ FAILED (rc=$rc). An empty context set is NOT 'no gates changed'. STOP."; exit 1; }
jq '{contexts: .contexts, checks: [.checks[].context],
     n_contexts: (.contexts | length), n_checks: (.checks | length)}' /tmp/e3-protection.json
# n_contexts and n_checks must both be 4 and neither may be null.
```

## Record skeletons

**FOUR skeletons follow, and all four live in `specs/001-codeql-coverage/evidence-log.md`**: the
probe record, the pre-merge verification, the baseline record and the close-out record. Copying
them faithfully is what makes that file's four `^## ` headers exist. A fifth deliverable,
`specs/001-codeql-coverage/enforcement-recommendation.md`, is a SEPARATE file written at close-out
and is not one of these skeletons; its required contents are listed under Phase F.

Dates in ISO 8601 (`YYYY-MM-DD`), per constitution Amendment 1.5.

### Probe record (FR-010, SC-010)

```markdown
## Probe record
- Dispatch available (A1): yes | no

### B1 evidence (Q4, no mutation). This section alone satisfies SC-009 and SC-010.
- Source: run 30581930915, job 91004036909, `refs/heads/main`, full-tree Python analysis
- Extractor invocation (log line 1480), verbatim: ...
- `Extracted file` lines total: 152 | under `/tests/`: 0
- Coverage summary (log line 2067), verbatim: ...
- Tracked `.py` files: 544 total, 393 under `tests/`, none of them in the database
- Conclusion: `paths-ignore` performs the exclusion at EXTRACTION time. The `tests/**` query filter
  is INERT. The line-13 comment is FALSE. Arms 1 and 2 are ANSWERED and were not run (FR-009b).

### B2 control arm (OPTIONAL, the only permitted mutation)
- Status: RUN | NOT RUN | NOT RUNNABLE (FR-009c)

| Arm | Config as run (verbatim) | Analysis id | Commit sha | Results under tests/ | Rule ids | Paths |
|---|---|---|---|---|---|---|
| 3 control | | | | | | |

- Does `py/incomplete-url-substring-sanitization` still fire on current Python test code? ...
- Filter decision: DELETE (only on a positive arm) | RETAIN unchanged (default whenever the arm is
  zero, not run, or not runnable, per FR-009b and FR-008)
- FR-011 resolution applied: ...
- FR-006 record: which shared config rules now reach the new leg, and their disposition
- FR-007 / FR-007a: the frontend/tests decision AND the asymmetry against excluded Python tests.
  **TRANSCRIBE the argument from Clarification Q4. Do not re-derive it**: Q4 wrote it in full, and
  a second argument invites one that disagrees with the first. The reason must name FR-008.
```

### Pre-merge verification (excluded from baseline)

```markdown
## Pre-merge verification (refs/heads/001-codeql-coverage)
- Analysis id: ...  <- EXCLUDED from baseline capture per FR-019
- SC-002 results count: ...
- SC-003 extracted files: frontend/ PROVEN (tier 1|2|3) | UNPROVEN, src/dashboard/ PROVEN (tier
  1|2|3) | UNPROVEN. **There is no `no` value.** Per the SC-003 anti-false-negative rule, silence
  in the log is UNPROVEN and carried as an open item. Writing "no" asserts a coverage gap that was
  never observed, which is the one recording SC-003 forbids. UNPROVEN does not fail the MERGE gate.
- SC-007 leg duration: ... / workflow total: ... / pre-change total: 5 to 7 min
- FR-004a resolution warnings observed in the job log: ...
```

### Baseline record (FR-013, FR-019, FR-020, FR-021)

```markdown
## Baseline record
- Source analysis id (refs/heads/main): ...
- Analysis timestamp: ... | Close-out date (+10 working days): YYYY-MM-DD
- Accountable role for triage: ...
- Open alert count before: 5 | after: ... | delta: ...   (SC-004; an increase PASSES)
- FR-004a resolution warnings: ...

| Path class | Alerts | Rule ids | Severities | Disposition |
|---|---|---|---|---|
| Product: frontend/src, src/dashboard | | | | |
| Test: frontend/tests | | | | |
| Non-shipping: build config, specs/ contract stubs | | | | |

- WINDOW: 10 working days, CONFIRMED by owner on YYYY-MM-DD
  | WINDOW: 10 working days, ASSUMED, Deferral 2 unanswered at capture
  (exactly one of those two literal strings; a blank field fails)
- Window extension (FR-016a, at most ONE): used? no | yes, new date YYYY-MM-DD, reason: <text>
```

### Close-out record (SC-008, SC-013)

Written on the recorded close-out date, NOT at merge. The three fields below sat in the baseline
skeleton until AR#3; they belong here, because they are the CLOSE-OUT gate and the baseline record
is written weeks earlier. The order of the first two is load-bearing and was made so at Q5: count
BEFORE the default is applied, because after the default every alert carries a disposition by
construction and SC-008 could never fail.

```markdown
## Close-out record
- **Undispositioned count at window close, BEFORE the FR-016b default is applied: N**
  (SC-008. Record the number even when it is zero, and record the undispositioned set verbatim
  alongside it. This number, and only this number, is what SC-008 is measured against.)
- Undispositioned set, verbatim: ...
- FR-016b default applied to that set as `carded follow-up`: yes | n/a (count was 0)
- Close-out outcome (SC-013): COMPLETE (count was 0) | FAILED CLOSE-OUT (count was non-zero)
- §9 registry entries written: npm ecosystem TD-___ and §10 local-SAST gap TD-___ at merge (D2);
  FR-016b lapse set TD-___ | n/a, only if the lapse path fired. Identifiers allocated AT WRITE
  TIME against the registry's then-highest value, never pre-reserved. The value read at merge is
  already stale by now, so re-read it.
- §9(b) labelled GitHub issues: OUTSTANDING, not raised. The owner has directed that the
  `tech-debt` label not be created and that no issue be raised against it, with the question
  audited once at the end of the campaign. Do not run `gh label create` or `gh issue create`, and
  do not substitute another label. Record this as outstanding rather than claiming §9 complete.
```

## Reminders that are easy to lose

- A rise in the open alert count is the expected outcome, not a regression (FR-014, SC-004). The
  alerts were always there. Nothing was looking.
- The feature stays OPEN after merge (FR-023). Two gates, not one.
- Never cite a green pull request check as coverage evidence (FR-018).
- No probe arm may reach `main` (FR-010a).
