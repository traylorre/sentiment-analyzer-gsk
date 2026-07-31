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
# A1: can we dispatch on the feature branch at all?
gh workflow run "$WF" --repo "$REPO" --ref "$BR" && echo DISPATCH_OK
gh run list --repo "$REPO" --workflow "$WF" --branch "$BR" --limit 3
```

```bash
# A2: snapshot the 5 open Python alerts BEFORE anything changes. SC-005 forbids any of them
# DISAPPEARING as a side effect of the config work, and that is only checkable against a
# pre-change list. Identity is the (rule, path) PAIR, never the alert number: closing an alert
# and rewriting the line spawns a fresh number at the same location, so a number-keyed diff
# reports a loss that did not happen. Numbers are kept only as a lookup convenience.
gh api "repos/$REPO/code-scanning/alerts?ref=refs/heads/main&state=open&per_page=100" --paginate \
  --jq '[.[] | {key: "\(.rule.id)@\(.most_recent_instance.location.path)",
                number, sev: .rule.security_severity_level}] | sort_by(.key)' \
  > /tmp/a2-prechange.json || { echo "A2 API READ FAILED, do not proceed"; false; }
test -s /tmp/a2-prechange.json || echo "A2 EMPTY: this is a read failure, not a clean repo"
```

Failure at A1 is not a blocker, it is an outcome, and after Q4 it is a small one: B1 needs no
dispatch, so only the OPTIONAL B2 arm is lost. Record it NOT RUNNABLE under FR-009c, retain the
query filter unchanged per FR-009b, keep B1 and B3, and take all User Story 1 evidence from
`refs/heads/main` after merge.

**A3: route the two Clarification DEFERRALS.** Neither has a home outside spec.md's Clarifications
appendix, which is where deferrals expire.

- **Deferral 2, the 10-working-day window (Q5). Ask the owner BEFORE Phase E.** FR-021 writes the
  computed close-out date into the baseline record at capture time and FR-016a allows exactly ONE
  extension. An answer arriving after E2 spends that single extension on an authoring correction
  instead of on alert volume. Unanswered at capture: record 10 working days as ASSUMED, say so in
  the baseline record, and treat a later change as the FR-016a extension.
- **Deferral 1, the stale constitution §9 path (Q2). Not blocking.** Carried into the F2
  enforcement recommendation so it reaches the same named decider under the same decision-by date.

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
  || { echo "LOG FETCH FAILED (rc=$rc). Every zero below is meaningless. STOP."; }
grep -c . /tmp/py-main.log                         # sanity: total log lines, must be large

grep -n 'filter exclude' /tmp/py-main.log          # extractor invoked with --filter exclude:tests/**/*
grep -c 'Extracted file' /tmp/py-main.log          # expect 152. If 0, the guard above failed.
grep 'Extracted file' /tmp/py-main.log | grep -c '/tests/'; echo "rc=${PIPESTATUS[0]}"
# ^ expect 0, and PIPESTATUS[0] must be 0 too. A 0 count with PIPESTATUS[0]=1 means the first
#   grep matched nothing, ie. the log is wrong or empty, NOT that no test file was extracted.
grep 'CodeQL scanned' /tmp/py-main.log             # "152 out of 154 Python files"
git ls-files '*.py' | grep -c '^tests/'            # expect 393, none of which are in the database
```

**B2, OPTIONAL, MUTATES**: run the control arm ONLY to decide whether to DELETE the inert query
filter as dead or RETAIN it against a future narrowing of the path exclusion.

```bash
# MUTATES: remove BOTH paths-ignore: tests/**/* and the py/... query filter, then
git commit -S -am "probe(001): codeql config control arm"
git push origin "$BR"
gh workflow run "$WF" --repo "$REPO" --ref "$BR"

gh api "repos/$REPO/code-scanning/analyses?ref=refs/heads/$BR&per_page=10" \
  --jq '.[] | {id, category, created_at, results_count, commit_sha}'

# Results MUST come from that analysis's SARIF, not from the alerts endpoint. An alert carries
# only `most_recent_instance`, which a later run on the same ref overwrites, so an alerts query
# reports the newest run twice and cannot separate two runs of one reference.
ID=<analysis id for this arm>
gh api "repos/$REPO/code-scanning/analyses/$ID" \
  -H "Accept: application/sarif+json" > "/tmp/arm-$ID.sarif"
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

# SC-002: the leg reports a results count
gh api "repos/$REPO/code-scanning/analyses?ref=refs/heads/$BR&per_page=10" \
  --jq '.[] | select(.category | test("javascript")) | {id, created_at, results_count}'

# SC-003 + FR-004a: both dashboards extracted, and any resolution warnings
RUN=$(gh run list --repo "$REPO" --workflow "$WF" --branch "$BR" --limit 1 --json databaseId --jq '.[0].databaseId')
JOB=$(gh run view "$RUN" --repo "$REPO" --json jobs \
  --jq '.jobs[] | select(.name=="Analyze (javascript-typescript)") | .databaseId')
gh run view "$RUN" --repo "$REPO" --log --job "$JOB" > /tmp/jsleg.log
rc=$?
# GUARD. The FR-004a check below treats EMPTY as good news ("no resolution warnings"), so a failed
# fetch would report a clean bill of health. Assert the log exists before believing any silence.
[ "$rc" -eq 0 ] && [ -s /tmp/jsleg.log ] \
  || { echo "JS LEG LOG FETCH FAILED (rc=$rc). Silence below is a read failure, not a result."; }

# TIER 1 (primary). Paths in these lines are ABSOLUTE runner paths appearing MID-LINE, after the
# "<job>\t<step>\t<timestamp>" prefix gh prepends. A line-anchored '^frontend/' returns 0
# UNCONDITIONALLY and is a guaranteed false negative. Match unanchored substrings.
grep 'Extracted file' /tmp/jsleg.log | grep -c '/frontend/'
grep 'Extracted file' /tmp/jsleg.log | grep -c '/src/dashboard/'

# TIER 2 (only if tier 1 emitted NO per-file lines at all). Per-file logging is extractor-specific
# and the JavaScript extractor exposes no logging-verbosity option, so silence here means
# "the log did not say", never "the directory was not extracted".
grep -E 'Calling |extractor|--filter' /tmp/jsleg.log | head -20

# TIER 3 (corroboration only; tolerance is wider than src/dashboard's 6 files)
grep 'CodeQL scanned' /tmp/jsleg.log
git ls-files '*.js' '*.jsx' '*.ts' '*.tsx' '*.mjs' '*.cjs' | grep -vcE '^tests/'   # expect 290

# FR-004a. EMPTY here means "no resolution warnings", which is the good outcome, so it is only
# believable if the guard above passed. Record which it was, never just "none found".
grep -iE 'could not resolve|module resolution|type resolution|no such module' /tmp/jsleg.log
echo "grep rc=$? (1 = genuinely no warnings, 2 = file unreadable)"

# SC-007: leg duration and workflow total
gh run view "$RUN" --repo "$REPO" --json jobs \
  --jq '.jobs[] | {name, started_at, completed_at}'
```

Record the analysis id from this step in the evidence log **as excluded from baseline capture**.

## Phase D. Merge, then discharge the §9 obligation

The feature stays OPEN after merge (FR-023). Before moving on, write the two UNCONDITIONAL tech
debt entries the Q2 triage identified. The Constitution Check in plan.md records §9 as PASS **with
obligation**; skipping this makes that row false.

```bash
# Allocate identifiers AT MERGE TIME against the registry's then-highest value. Never pre-reserve:
# TD-024 is contested by sibling features, and pre-reserving is what created that collision.
grep -oE 'TD-[0-9]{3}' docs/reference/TECH_DEBT_REGISTRY.md | sort -u | tail -1
```

Two entries plus a `tech-debt`-labelled issue each, per constitution §9(a) and §9(b):

1. npm ecosystem absent from `.github/dependabot.yml` while 82 npm advisories are open (F18).
2. The §10 local-SAST gap: `make sast` covers `src/` only, so after this lands CodeQL covers
   `frontend/` and no local pre-push tier does.

A third, conditional entry is owed only if the FR-016b lapse path fires at close-out.

## Phase E. Baseline (after merge only)

```bash
# E1: the FIRST refs/heads/main javascript-typescript analysis after merge
gh api "repos/$REPO/code-scanning/analyses?ref=refs/heads/main&per_page=30" \
  --jq '[.[] | select(.category | test("javascript"))] | sort_by(.created_at) | .[0]'

# E2: the baseline alert set. Filter to state=open so it is the SAME population A2 captured,
# otherwise the SC-004 "before 5 / after N" delta compares open-only against all-states.
# Then split off the JavaScript/TypeScript rules: the baseline FR-016 and SC-008 are defined over
# is the JS/TS set, and the 5 pre-existing Python alerts are explicitly Out of Scope.
gh api "repos/$REPO/code-scanning/alerts?ref=refs/heads/main&state=open&per_page=100" --paginate \
  --jq '[.[] | {number, rule: .rule.id, sev: .rule.security_severity_level,
                path: .most_recent_instance.location.path}]
        | {total_open: length,
           jsts: [.[] | select(.rule | startswith("js/"))],
           python: [.[] | select(.rule | startswith("py/"))]}'

# E3 SC-005: Python floor of 9, unchanged
gh api "repos/$REPO/code-scanning/analyses?ref=refs/heads/main&per_page=30" \
  --jq '[.[] | select(.category | test("python"))] | .[0] | {id, results_count}'

# E3 SC-006: exactly four required contexts, unchanged
gh api "repos/$REPO/branches/main/protection/required_status_checks" --jq '.contexts'
```

## Record skeletons

Both live in `specs/001-codeql-coverage/evidence-log.md`. Dates in ISO 8601 (`YYYY-MM-DD`), per
constitution Amendment 1.5.

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
- FR-007 / FR-007a: the frontend/tests decision AND the asymmetry against excluded Python tests,
  argued or carded. Not left undiscussed.
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

- Window duration: 10 working days, CONFIRMED by owner | ASSUMED (Deferral 2 unanswered at capture)
- Window extension (FR-016a, at most ONE): used? no | yes, new date + reason
- **Undispositioned count at window close, BEFORE the FR-016b default is applied: N**
  (SC-008. Record the number even when it is zero. Measured after the default it is always zero
  by construction and the criterion could never fail.)
- Close-out outcome (SC-013): COMPLETE (count was 0) | FAILED CLOSE-OUT (count was non-zero)
- §9 registry entries written (D2): npm ecosystem TD-___, §10 local-SAST gap TD-___,
  FR-016b lapse set TD-___ | n/a. Identifiers allocated at merge time, never pre-reserved.
```

## Reminders that are easy to lose

- A rise in the open alert count is the expected outcome, not a regression (FR-014, SC-004). The
  alerts were always there. Nothing was looking.
- The feature stays OPEN after merge (FR-023). Two gates, not one.
- Never cite a green pull request check as coverage evidence (FR-018).
- No probe arm may reach `main` (FR-010a).
