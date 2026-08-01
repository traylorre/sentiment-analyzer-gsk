# Implementation Plan: Close CodeQL alert 144 (OAuth provider taint)

**Branch**: `001-oauth-provider-taint` | **Date**: 2026-07-30 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-oauth-provider-taint/spec.md`

## Summary

Delete every `provider`-derived value from the `logger.info()` `extra` context in
`store_oauth_state()` (`src/lambdas/shared/auth/oauth_state.py`), which is the exact shape that
carries a non-null `fixed_at` on alerts 26, 27, 106, 107, 110 and 111 after `ebcc2f4`. That means
removing the `"provider": safe_provider` entry and the now-unused `safe_provider` sanitizer
assignment above it. Nothing is substituted in its place: the `extra` dict is never rendered by any
handler in this repository, so there is no operational capability to preserve, and `provider`
remains persisted in the DynamoDB item written eight lines earlier.

One caveat on how far that precedent transfers, carried here from spec.md and research.md so the
implementer does not have to go looking for it: `ebcc2f4` did not delete its value outright, it
relocated the sanitized identifier into a raised exception message, a sink the analyzer tolerates.
`store_oauth_state()` is `put_item`, log, return, with no raise anywhere on its path, so no
equivalent relocation target exists and this deletion is strictly more aggressive than the shape it
cites. That is a reason to expect the fix to hold, not a reason to doubt it, but the precedent is
being stretched and the artifacts say so rather than claiming an exact match.

Verification is a single evaluation of the spec's decision gate against one completed default-branch
CodeQL analysis whose commit contains the change, read from the code scanning alerts API and scoped
to the path `src/lambdas/shared/auth/oauth_state.py` plus the rule id
`py/clear-text-logging-sensitive-data`. Never to an alert number, never to a line number, and not to
a function: this file already produced a respawn from line 95 to line 104 in a single analysis run,
this change itself shifts every line below the sink, and the alerts API exposes no function field at
all, so function attribution is derived from a line number and cannot be the criterion. Attribution
happens, per FR-006a, but only to decide who owns a survivor.

## Technical Context

**Language/Version**: Python 3.13 (Lambda runtime and local `.venv`; `requires-python = ">=3.13"`).
**Primary Dependencies**: None added, removed, or upgraded. The edit touches one stdlib `logging.Logger.info()` call already present in the file. Verification tooling is already installed: the GitHub CLI (`gh`) for the code scanning alerts and analyses APIs, plus `pytest` and `ruff` from `requirements-dev.txt`.
**Storage**: DynamoDB, unchanged. `provider` continues to be persisted in the item written by `table.put_item()` at `oauth_state.py:87`. No table, key, index, or item-shape change.
**Testing**: `pytest tests/unit/auth/` (30 tests, green at baseline; `store_oauth_state` covered by `TestStoreOAuthState` with a `MagicMock` table fixture, no moto needed). One new caplog-based regression assertion is added. Closure evidence comes from `gh api .../code-scanning/alerts` against `refs/heads/main`, not from any test.
**Target Platform**: AWS Lambda (`python3.13`), dashboard Lambda OAuth authorize path.
**Project Type**: Single project. One backend source file edited, one unit test file extended.
**Performance Goals**: N/A. The change strictly removes work (three `str.replace()` calls and a slice per authorize).
**Constraints**: FR-003 (runtime behavior outside the log call unchanged: stored item, returned `OAuthState`, PKCE verifier); FR-004 (`validate_oauth_state()` not modified); FR-010 (no rule suppression, no severity change, no file exclusion, no inline suppression comment); FR-013 (the sink carries a mandatory documentation comment naming the rule id, on every gate branch); inherited via FR-008 from `specs/001-ingestion-arn-logging/codeql-logging-convention.md` §4 (`src/lambdas/shared/secrets.py` MUST NOT be edited, its alerts 22-25 sit behind sticky dismissals with null `fixed_at` and re-fingerprint on touch); GPG-signed commits; no new AWS resources.
**Scale/Scope**: One function. Three lines deleted (`safe_provider` assignment), one dict entry deleted, one documentation comment added, one test method added. Under 20 lines changed in total.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against `.specify/memory/constitution.md`. **Re-keyed 2026-07-31**: this table cited
§6, §7, §8, §9 and §10 of the pre-prune document. `001-constitution-prune` renumbered the
constitution to five sections and deleted the tech-debt and local-SAST sections outright. Verdicts
are unchanged; the §9 row is the one whose obligation actually changed.

| Gate | Status | Justification |
|------|--------|---------------|
| §3 Testing, New code (unit tests; happy path plus one error path; 80% coverage floor) | PASS | No new function or module is introduced, so the "new code" coverage clause is vacuous. The gate is nevertheless satisfied actively rather than by exemption: a caplog assertion is added to `TestStoreOAuthState` proving no `provider` attribute reaches the emitted `LogRecord`. That is the only durable guard against a later refactor silently reintroducing the sink, which is the failure mode this file has already suffered once. |
| §3 Testing tiers (unit tests mock everything; `moto` for AWS) | PASS | The touched suite is `tests/unit/auth/`, which uses a `MagicMock` DynamoDB table. No AWS call, no preprod dependency. |
| §3 Testing (external publishers mocked everywhere except `@external-api`) | PASS | No external API is involved. `gh api` is a verification-time operator action against GitHub, not a test dependency. |
| §3 Testing, Dates (no `date.today()` / `datetime.now()` / `time.time()` in tests) | PASS | The added assertion is time-independent. The production `datetime.now(UTC)` at `oauth_state.py:78` is untouched and is source code, not a test. |
| §4 Push rules (`make validate`, `make test-local`, GPG-signed commit, feature branch, never main) | PASS | Standard flow. Note the `safe_provider` assignment MUST be deleted, not merely orphaned: `[tool.ruff.lint] select` includes `F`, so a retained unused local fails `ruff check` with F841 and blocks the required `Lint` context. |
| §2 Security (do not suppress a SAST finding without documented justification) | PASS | This feature removes an instance of exactly that pattern class rather than suppressing it. Neither tool's configuration is touched, and FR-010 forbids the suppression route the constitution's "DO NOT suppress without documented justification" clause is aimed at. |
| §2 Security (request logs are structured; raw input text is not logged by default) | PASS | `provider` is not raw input text, and this is not a request log. (The pre-prune §6 named request id, model_version, latency and outcome as the required fields; `provider` was none of them either. The rebuilt §2 dropped the field list, so this row no longer turns on it.) The field is also unrendered in production today (evidence: `specs/001-lambda-log-visibility/evidence/post-deploy/logshape-dashboard.json`), so no telemetry, metric filter, alarm, dashboard or runbook loses an input. The repository's only log metric filter is `dashboard_import_errors`. |
| §5 Pointers (tech debt lives on `CLEANUP-BOARD.html`) | PASS on the Confirmed branch; **conditional on the Refuted branch** | A code fix that closes the finding creates no debt. A dismissal is a documented security shortcut and must be recorded as a `CLEANUP-BOARD.html` card carrying location, evidence and next action. **No TD-XXX identifier is needed.** FR-007 and SC-006 in spec.md carry the obligation. |
| Standing owner constraint: no new AWS resources | PASS | Nothing infrastructural. No Terraform file is touched. |

**Post-design re-check (after Phase 1)**: unchanged. All gates PASS, with the tech-debt obligation
still conditional on which gate branch the analysis selects. No Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-oauth-provider-taint/
├── spec.md              # Stage 1 + Adversarial Review #1 appendix
├── plan.md              # This file
├── research.md          # Phase 0: decision record and prior-art ledger (satisfies US3 / FR-012)
├── quickstart.md        # Phase 1: verification and dismissal runbook
└── tasks.md             # Phase 2 output (/speckit.tasks, not created here)
```

**Artifacts deliberately not produced.** The plan template's Phase 1 asks for `data-model.md` and
`contracts/`. Neither has content here and both are omitted rather than padded:

- **`data-model.md`**: this feature introduces, removes and alters zero entities. The only data
  structure in scope is a `dict` literal passed as `logging`'s `extra` keyword, and it is losing one
  key. The persisted item and the returned `OAuthState` model are frozen by FR-003.
- **`contracts/`**: no interface is exposed or changed. `store_oauth_state()` keeps its exact
  signature, its return type and its DynamoDB write. The two production call sites are not touched.
  There is no API surface, no CLI surface and no schema to contract against.

### Source Code (repository root)

```text
src/lambdas/shared/auth/oauth_state.py   # store_oauth_state(): delete lines 99-101 (safe_provider
                                         #   assignment) and the "provider" entry at line 105;
                                         #   add a documentation comment naming the rule id.
                                         #   validate_oauth_state() (lines 253-258) NOT touched.
tests/unit/auth/test_oauth_state.py      # TestStoreOAuthState: add one caplog regression assertion.
```

**Structure Decision**: No structural change. Two existing files are edited in place. Nothing is
created or deleted outside `specs/001-oauth-provider-taint/`. In particular
`src/lambdas/shared/secrets.py` and `src/lambdas/ingestion/handler.py` are not opened; the latter
belongs to sibling feature `001-ingestion-arn-logging`, and file disjointness between the two
features is confirmed.

## Implementation Design

### The edit

`store_oauth_state()` currently reads, at lines 99 to 109:

```python
    safe_provider = (
        str(provider).replace("\r\n", " ").replace("\n", " ").replace("\r", " ")[:200]
    )
    logger.info(
        "OAuth state stored",
        extra={
            "provider": safe_provider,
            "has_user_id": user_id is not None,
            "ttl_seconds": OAUTH_STATE_TTL_SECONDS,
        },
    )
```

It becomes:

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

Four properties of that diff carry weight:

1. **The `safe_provider` assignment is deleted, not orphaned.** `provider` is its only input and the
   `extra` entry was its only consumer, so retaining it would be dead code and would fail
   `ruff check` under F841, blocking the required `Lint` context. It also has to go on the merits:
   FR-001 forbids any value derived from `provider` by replacement or slicing from reaching the
   context, and leaving the derivation alive next to the sink is precisely the shape `8424cbd` left
   behind.
2. **Nothing is substituted.** Not a literal, not an allowlist-selected constant, not a boolean.
   Adversarial Review #1 deleted the allowlist "Form A" for cause and it must not return: `extra` is
   not rendered, so a substitute preserves nothing, and it would require editing this sink a second
   time on a sink with a documented respawn.
3. **The comment is required, and it is documentation rather than suppression.** Clarification Q1
   promoted it from a plan-level choice to **FR-013**: it is mandatory on every gate branch,
   including the confirmed one. It carries no `# nosec`, no `# noqa`, no `# lgtm`, and no CodeQL
   alert-suppression pragma. FR-010 forbids an inline suppression comment as a substitute for the
   dismissal path; so constrained, this comment is not that, and FR-013 states the disjointness
   explicitly so the two requirements cannot be read as contradictory. It is also the mechanism by
   which US3's second acceptance scenario survives in the code rather than only in these artifacts,
   which matters because whoever writes the refactor that would reintroduce the key is looking at
   the file, not at `specs/`. The obligation is inherited via FR-008 from
   `specs/001-ingestion-arn-logging/codeql-logging-convention.md` §1, whose closing paragraph makes
   the site comment unconditional.
4. **`validate_oauth_state()` is not touched.** Its `safe_provider_validated` at line 253 and its
   `extra={"provider": safe_provider_validated}` at line 258 are a materially different case,
   request-derived provenance, and FR-004 freezes them. They carry no open alert.

### The regression assertion

Added to `TestStoreOAuthState` in `tests/unit/auth/test_oauth_state.py`. It calls
`store_oauth_state()` under `caplog` and asserts the emitted `LogRecord` has no `provider`
attribute, while `has_user_id` and `ttl_seconds` remain. `logging` promotes every `extra` key to a
record attribute, so this is a direct assertion on the sink's contents and not on rendered text,
which matters because the rendered text is bare in production and would pass either way. It uses no
date or time function, satisfying the constitution's deterministic-time clause.

No existing assertion changes, satisfying FR-011 and SC-004.

## Verification Design

The gate is evaluated **once**, against **one** completed default-branch analysis whose commit
contains the change. Copy-pasteable commands, the analyzed-ref requirement, the freshness proof and
every terminal state are in [quickstart.md](quickstart.md). The design in summary:

1. **Establish the closure query.** Closure is read from the alerts API filtered to
   `ref=refs/heads/main`, rule `py/clear-text-logging-sensitive-data`, path
   `src/lambdas/shared/auth/oauth_state.py`. That triple is the criterion, and an empty result on a
   successful, **paginated** call is the pass condition. Per FR-009 no pull request check result is
   admissible; the `Analyze` job on a PR reports into the PR's own ref, not the default branch's.

   Pagination is load-bearing rather than hygienic, because emptiness is the pass condition here.
   Measured on this repository 2026-07-30: an unpaginated alerts query returns **zero** open alerts
   and exits **0** on a repository carrying five, since the default page size is 30 against a corpus
   of 137 and the open alerts sit at numbers 144 to 150. `per_page=100` is not a fix; page one at that
   size spans numbers 180 down to 59 and drops alerts 22 to 27, the `secrets.py` sanitize-in-place
   sites this feature's evidence rests on. The query therefore uses `--paginate --slurp` into a file,
   filtered by standalone `jq`, and asserts a corpus floor plus a positive control before an empty
   result is read as `CONFIRMED`. `--slurp` cannot be combined with `--jq`, and `--paginate` without
   `--slurp` applies `--jq` per page, so the file-plus-`jq` shape is the only one that yields a single
   answer with an uncorrupted exit code. quickstart.md Step 3a and tasks.md T020 and T021 carry it.
2. **Prove the analysis is not stale.** The gate's fourth row exists because a result predating the
   change decides nothing. Freshness is proved by comparing the analysis `commit_sha` against the
   merge commit that landed the change:
   `gh api repos/OWNER/REPO/compare/<CHANGE_SHA>...<ANALYZED_SHA>` must report status `ahead` or
   `identical`. Anything else means the change is not in the analyzed tree and the observation is
   discarded.
3. **Attribute a survivor, at the analyzed commit.** This step runs only when step 1 returns a
   non-empty result, and it never licenses a pass. A survivor's `start_line` is mapped to a function
   by fetching `oauth_state.py` **at the analyzed commit** and locating the `store_oauth_state`
   definition bounds there, computed fresh per analysis and never carried from authoring time. The
   mapping is derived and best-effort by necessity: the alerts API carries no function field, only
   `path` and line and column bounds. Its sole output is ownership, whether the survivor is this
   feature's (dismiss, FR-007) or belongs to the FR-004-frozen `validate_oauth_state()` sink and must
   be reported instead (FR-006a).
4. **Classify, once.** Five observations map to five actions, per the spec's Decision Gate table. A
   new alert number for this rule on this path is **Refuted**, not success, regardless of what
   happened to 144.
5. **Terminal states.** Exactly seven, and the feature must end in one of them. `PENDING-BRANCH-ANALYSIS`
   was added after the Stage 7 cross-artifact analysis found that FR-008 binds this feature to the
   convention **in full** while this table carried only one of the two terminal states
   `codeql-logging-convention.md` §5 defines. It is the likeliest ending of the three that are neither
   done nor failed, and without it an implementing agent whose change has not landed has no state to
   record:

| Terminal state | Reached when | What is recorded |
|---|---|---|
| `PENDING-BRANCH-ANALYSIS` | The code change and its regression guard are complete and green, but the change has not landed on `main`, so no qualifying default-branch analysis can exist | The gate is not evaluated. Record the code change as complete and write the closure query, filled in with this feature's path and rule id, so the check is mechanical the moment it lands. Inherited from `specs/001-ingestion-arn-logging/codeql-logging-convention.md` §5a, which calls it "the normal ending, not an edge case". Neither done nor failed. Distinct from `BLOCKED-NO-ANALYSIS`, whose 7-day clock starts only once the change is on `main`. |
| `CONFIRMED` | No open finding for this rule on `oauth_state.py` in a fresh analysis | The analysis id and its `commit_sha`. `fixed_at` on alert 144 is recorded as **corroboration only**, never as the criterion: the criterion is the path being free of open findings, and 144 is a locating label. Stop. No dismissal. |
| `REPORTED-FOREIGN-SINK` | A finding for this rule survives on the path but attributes outside `store_oauth_state()` | Reported to the owner per FR-006a. Not Confirmed, and not dismissed here: `validate_oauth_state()` is frozen by FR-004 and carries the same sanitize-in-place shape at lines 253 to 258. The code change is independently complete. |
| `REFUTED-DISMISSED` | A finding survives; the maintainer dismisses it as `false positive` with the three-element justification | The alert number, the exact justification text, the API response, and a `CLEANUP-BOARD.html` kanban card per FR-007 and the tech-debt conditional gate. No TD identifier is allocated. |
| `BLOCKED-ON-OWNER` | A finding survives and the **read-only probe** of convention §5b (token scopes read together with repository visibility and the actor's repository permissions) resolves to *absent*. Never established by attempting a dismissal. **A missing `security_events` scope is not by itself the trigger**: GitHub requires that scope only on private repositories, and on this public one `repo` subsumes `public_repo`, which is what the endpoint needs. Probed 2026-07-30 the local environment resolves to *available*, so this is not the expected ending | A handoff artifact in this directory carrying the observed alert numbers, the exact justification text for each, and the exact API call. The code change is independently complete and mergeable. Inherited via FR-008 from `specs/001-ingestion-arn-logging/codeql-logging-convention.md` §5, not newly defined here. |
| `BLOCKED-NO-ANALYSIS` | No completed default-branch analysis covering the change within **7 days** of the change landing on `main` | Reported to the repository owner naming the missing analysis. Not classified. Not dismissed. Terminal, not a further attempt. |
| `BLOCKED-REGRESSION` | The unit suite fails, or a new open alert is attributable to this feature's diff (SC-003) | Reported before any gate evaluation. The gate is not evaluated on a broken tree. A repo-wide open-alert count is NOT the trigger: sibling `001-codeql-coverage` is expected to raise that number, and the owner's directive is that coverage is the goal, not a low count. |

The 7-day bound is generous against observed behavior: the `codeql` job lives in
`.github/workflows/pr-checks.yml`, which triggers on `push` to `main`, and the three most recent
default-branch analyses landed within roughly 25 minutes of their commits. The bound covers a
workflow outage, not normal turnaround.

**On what a green build is worth here.** CodeQL is not a required status check. The required
contexts are exactly `Secrets Scan`, `Lint`, `Run Tests` and `Playwright E2E Tests`, and the
rulesets API returns `[]`. The `Analyze` job passing tells you the analysis ran, never that the
alert closed. Only the alerts API tells you that.

## Phase Notes

**Phase 0 (research)**: complete. `research.md` holds the decision record, the prior-art ledger keyed
on `commit_sha` and `fixed_at` rather than on dates or `state`, and the two questions that are
deliberately left unresolved. There were no NEEDS CLARIFICATION markers to resolve: spec.md, after
Adversarial Review #1, fixes the approach to a single form and leaves no technical choice open.

**Phase 1 (design)**: complete, minus the two artifacts documented as skipped above.

**Agent context update not run.** The workflow's Phase 1 step 3 calls
`.specify/scripts/bash/update-agent-context.sh claude`, which writes the repository-root `CLAUDE.md`.
Three sibling agents share this worktree and this feature's write scope is
`specs/001-oauth-provider-taint/` only, so the script was deliberately not executed. It would have
had nothing to add regardless: this feature introduces no language, dependency or storage technology
that is not already listed there.

## Gaps found in spec.md

Both were raised in Stage 4 clarification and are now **closed in spec.md itself**. Retained as a
record of what was found and how it was resolved.

1. **No terminal state for absent dismissal permission.** spec.md Assumption 2 asserts the maintainer
   can dismiss, and the gate's Refuted row routed straight to FR-007, with nothing covering the case
   where the implementing agent lacks `security-events: write`. CLOSED by clarification Q3. The old
   FR-008 bound only the dismissal justification's wording and recording location, so it did not in
   fact reach the sibling's terminal state and the plan's "inherited via FR-008" citation was
   unsupported. FR-008 is now widened to consume
   `specs/001-ingestion-arn-logging/codeql-logging-convention.md` in full, which carries
   `BLOCKED-ON-OWNER` at §5, so the inheritance is real rather than asserted.
2. **The tech debt obligation is never mentioned.** A CodeQL dismissal is a documented security
   shortcut and must be recorded. CLOSED by clarification Q2: the obligation lives in FR-007 and
   SC-006. A dismissal is recorded as a `CLEANUP-BOARD.html` card with no identifier to allocate.

## Complexity Tracking

No constitution violations. Table intentionally empty.

---

## Adversarial Review #2

Reviewer did not author these artifacts. Focus is drift introduced by the Stage 4 clarification
answers, which are written into spec.md only and never propagated to plan.md, research.md or
quickstart.md, plus cross-artifact consistency. Adversarial Review #1's findings are not re-litigated.
Every API-shaped and tool-shaped claim below was re-derived by running the thing, not by reading
about it.

### A. Drift from the clarification session

| # | Sev | Clarification | Artifact left stale | Finding and correction |
|---|---|---|---|---|
| D1 | HIGH | Q1 (new FR-013) | `research.md:35` | The Alternatives table rejected "Inline suppression comment ... Forbidden by FR-010" with no carve-out. After Q1 the feature **mandates** an inline comment at that exact site. A reader of research.md alone would conclude the FR-013 comment is forbidden, which is precisely the reading Q1's answer went to the trouble of pre-empting inside spec.md and then failed to carry across. **FIXED**: row narrowed to name the four suppression pragmas explicitly and to point at the new Decision 5. |
| D2 | HIGH | Q1 (US3 gained a second acceptance scenario) | `research.md:5` | research.md opens "Its test is the US3 acceptance scenario", singular, and describes only the first. US3 now has two, and the second (a reader with only the source file is warned at the sink) is **unsatisfiable by this file by construction**. The artifact claimed a passing grade against a requirement it cannot meet. **FIXED**: reworded to claim the first scenario only, and to state that the second is discharged in code by FR-013. |
| D3 | HIGH | Q1 (new FR-013) | `research.md`, whole file | FR-013 had no representation in research.md at all, yet the comment text mandated by plan.md and quickstart.md **points the reader at research.md** ("See specs/001-oauth-provider-taint/research.md before adding a key here"). The pointer resolved to a document that never mentioned the comment or its FR-010 disjointness. **FIXED**: added **Decision 5**, covering the obligation, why the sink is marked unconditionally, and why FR-010 and FR-013 partition rather than conflict. |
| D4 | HIGH | Q3 (FR-008 widened to require citing the convention document's sections, never a sibling requirement number) | `research.md:141` | research.md cited the blast-radius prohibition as "sibling feature `001-ingestion-arn-logging` FR-013". That is exactly the fragile form widened FR-008 now forbids, so the artifact violated its own feature's requirement. The number happens to be correct today (`specs/001-ingestion-arn-logging/spec.md:96`), which makes it worse, not better: it will rot silently. **FIXED**: re-anchored on `codeql-logging-convention.md` §4, with the reason stated inline. |
| D5 | HIGH | Q1 (new SC-007) | `quickstart.md`, `plan.md` terminal-state table | SC-007 requires the FR-013 comment to be present on the merged file with no suppression pragma, "verifiable by inspecting the merged file". **No artifact contained a verification step for it.** Step 1c ran format, lint, tests and `make validate`; Step 4a recorded analysis id, `commit_sha`, `fixed_at` and an SC-003 recount; Step 4b recorded the dismissal and the registry entry. SC-007 appeared in none of them. A success criterion nobody checks is decoration. **FIXED**: added an SC-007 check to quickstart Step 1c (grep for the rule id in the preceding comment block, assert absence of the four pragmas) and a re-run instruction in Step 4a. |
| D6 | MEDIUM | Q3 (FR-008 widened to consume the convention in full, which carries `BLOCKED-ON-OWNER` at §5) | `spec.md` Assumptions | Assumption 2 still read, flatly, "The maintainer can dismiss a code scanning alert ... permission and precedent are both established". That is the exact assumption Q3 spent a terminal state removing. plan.md's "Gaps found" section claims this was "CLOSED in spec.md itself"; the requirement was closed, the assumption that motivated it was not. **FIXED** (single edit): rewritten to separate "some actor holds the permission" from "the implementing agent holds it", and to route the second case to `BLOCKED-ON-OWNER` via §5. |

### B. Cross-artifact inconsistencies

| # | Sev | Finding |
|---|---|---|
| X1 | HIGH | **The gate's primary query does not execute.** `quickstart.md:169` (pre-fix) read `gh api ... --jq --arg rule "$RULE" --arg file "$FILE" '[...]'`. `gh api` has **no `--arg` flag**; its only jq flag is `--jq`/`-q`, taking one expression. Verified against `gh api --help` on this machine. The single most load-bearing command in the runbook, the one that reads the decision gate, fails on invocation. Worse than that, the natural repair (piping into standalone `jq`) sets the trap the campaign's own rule warns about: a failed `gh api` piped into `jq` prints nothing, and empty output **is the documented pass condition**, so a read failure renders as `CONFIRMED`. **FIXED**: variables interpolated into a single `--jq` expression, with an explicit `gh exit=$?` echo and a sentence stating that `[]` is only a pass when the exit code is 0. |
| X2 | HIGH | **SC-003 makes this feature's success depend on a sibling doing its job.** `spec.md:291` (pre-fix) required the repo-wide open-alert count to be "no higher after this feature than the baseline of 5". Sibling `001-codeql-coverage` enables an additional analysis leg and states at `specs/001-codeql-coverage/spec.md:15` that this "will very likely RAISE the open alert number"; its own SC-004 (`:427`) explicitly refuses to fail on a rise, and its acceptance scenario at `:91` records the rise as expected outcome. The owner's directive governing the campaign is that coverage is the goal, not a low alert count. As written, SC-003 fails this feature for a sibling doing exactly what it was asked to do, and it is the mirror image of fact-checking on alert numbers that AR#1 spent three findings removing. Propagated into `plan.md:201` as a **blocking** terminal state (`BLOCKED-REGRESSION`) and into `quickstart.md:41` as a hard stop before the work even starts. **FIXED in all three**: SC-003 restated as an attribution test with three conditions wholly inside this feature's control (no new alert in `store_oauth_state()`, none new on `oauth_state.py`, none new on `secrets.py`); the terminal state retriggered on attribution; quickstart Step 0 now records the baseline set rather than gating on its count, and names which sibling owns each expected movement. |
| X3 | HIGH | **SC-001 and the decision gate could return opposite answers on the same evidence.** `spec.md:287` scoped SC-001 to the whole **path** `src/lambdas/shared/auth/oauth_state.py`. FR-006, the Decision Gate's scoping paragraph, plan.md's verification design and `quickstart.md:196` all scoped to the **function** `store_oauth_state()`, and quickstart 3c scored "every finding maps outside `store_oauth_state()`" as **Confirmed**. So an open finding at the path could return Confirmed from the gate and FAIL from SC-001 at the same time. Not hypothetical: `validate_oauth_state()` carries `extra={"provider": safe_provider_validated}` at `oauth_state.py:258`, the identical sanitize-in-place shape whose `fixed_at` is null to this day on alerts 22 through 25, and FR-004 freezes it. **FIXED, and the fix direction was reversed mid-review** (see the note below): the gate is now keyed on **path plus rule id**, matching SC-001 as originally written and matching the inherited convention §3 Trap 2. FR-006 rewritten, gate scoping paragraph rewritten, plan verification step 3 and quickstart 3b demoted to survivor attribution, research.md Decision 4 retitled. New **FR-006a** and a sixth terminal state `REPORTED-FOREIGN-SINK` handle the real case the function scoping was reaching for: a survivor attributing to the FR-004-frozen sink is reported to the owner, never dismissed here and never scored Confirmed. |
| X4 | HIGH | **`make validate` cannot pass on this tree, and the runbook prescribes it with no caveat.** `quickstart.md:118` instructed `make validate`. `Makefile:42` chains `check-banned-terms`, and `scripts/check-banned-terms.sh` exits **1** today on 17 pre-existing matches in other features' spec directories, one of which is the unfilled plan-template placeholder at `specs/1268-cors-404-headers/plan.md:21`. Verified by running it. An implementer following the runbook hits a red gate caused by files this feature is forbidden to touch, and the two available reactions are both bad: edit a sibling's directory, or start disregarding the gate. **FIXED**: Step 1c now runs `make sast` directly, states the pre-existing failure and its cause, confirms this feature's own directory is clean, and instructs that other features' directories are not to be repaired here. |
| X5 | MEDIUM | **plan.md asserted the `ebcc2f4` precedent without the caveat that limits it.** spec.md and research.md both carry it: `ebcc2f4` did not delete its value, it relocated the sanitized identifier into a raised exception message, and `store_oauth_state()` has no raise on its path, so this deletion is strictly more aggressive than the shape it cites. plan.md's Summary asserted the shape match with no qualifier, and plan.md is the artifact the implementer reads first. **FIXED** (one paragraph added to Summary). |
| X6 | LOW | `plan.md` Source Code block describes `validate_oauth_state()` as "(lines 253-258)". Those are the sink lines inside it; the function's `def` is at line 154 and it runs to end of file (260). Verified. Not corrected: the intent is unambiguous and the numbers are the ones the reader needs. |
| X7 | LOW | `plan.md` Scale/Scope enumerates the diff as "three lines deleted, one dict entry deleted, one documentation comment added, one test method added" and omits the `import logging` addition that `quickstart.md:85` requires. Recorded, not corrected. |
| X8 | LOW | `research.md` Decision 4 says the change "deletes four lines from the middle of the function, which shifts every line below 99". True of the deletion alone; the mandated four-line FR-013 comment lands in the same place, so the net shift is approximately zero. Harmless, because the gate is function-scoped precisely so that no line arithmetic matters. Recorded, not corrected. |
| X10 | HIGH | **The spec's own US2 Independent Test keyed on alert 144 reaching a state.** `spec.md:157` read "query the alert-state API and confirm alert **144** reports `dismissed`". That is the exact hazard this feature exists as the proof of: `8424cbd` closed 117 and opened 144 at the identical timestamp, so a correctly handled respawn dismisses a *different* number and this test fails, while an unhandled disappearance of 144 passes it. Found only by re-reading the source spec **after** the derived artifacts had been checked: plan.md and quickstart.md both already forbade alert-number keying (quickstart's anti-checklist calls it out by name), so the derived artifacts looked clean and were weak evidence about the source. Drift in this pipeline runs source to derived, so a clean derived artifact proves little about the spec. **FIXED**: re-keyed on the path plus rule id being free of open findings, with 144 demoted to a locating label and the failure mode stated. Two derived-artifact echoes demoted alongside it: the `CONFIRMED` terminal-state row in plan.md and quickstart Step 4a now record alert 144's `fixed_at` as corroboration only, never as the criterion. |
| X9 | LOW | `quickstart.md` Step 3b pipes `gh api ... \| base64 -d \| grep -n '^def '` and reads the result without checking `PIPESTATUS[0]`. A failed fetch yields no matches, which reads as "no functions found" rather than as an error. Lower severity than X1 only because the failure mode is visibly absurd rather than silently green. Recorded, not corrected. |

### C. The TD-024 pre-reservation, all four sites

Confirmed cross-feature conflict, and this feature was the last holdout still asserting the claim.
Three features reason from the same `TD-023` high-water mark: `001-ruff-bump-forward` task T016
(`tasks.md:36`) claims "the next sequential TD entry"; `001-codeql-coverage` Phase F writes registry
entries; and this feature named the number outright. Both siblings had already independently settled
on merge-time allocation and said so on the record (`specs/001-ingestion-arn-logging/spec.md:249`,
`specs/001-codeql-coverage/plan.md:282`, the latter naming this feature as the claimant). Severity
**HIGH**: two features writing `TD-024` into a shared registry file is a merge conflict at best and a
duplicated identifier in a compliance artifact at worst.

A dismissal is recorded as a
`CLEANUP-BOARD.html` card with no identifier.

### D. Checks run that produced no finding

Recorded so a later reader knows these were tested rather than assumed.

- **No surviving live reference to the deleted "Form A".** All three mentions (`spec.md` "Why
  deletion, and not a substituted literal", `research.md` alternatives table, `quickstart.md` Step 5
  anti-checklist) frame it as deleted for cause and forbidden. None resurrects it.
- **The regression test fails on unfixed code**, which is the whole point of fact 7. It asserts
  `not hasattr(records[0], "provider")` on the `LogRecord`, and `logging` promotes every `extra` key
  to a record attribute, so today's code sets `.provider` and the assertion fails. No `caplog.text`
  assertion exists anywhere in the artifacts.
- **Test preconditions hold.** `tests/unit/auth/test_oauth_state.py` does **not** currently import
  `logging` (so quickstart 1b is right to add it) and **does** already import
  `OAUTH_STATE_TTL_SECONDS`. Verified by reading the file.
- **Every line citation into `oauth_state.py` is correct.** `safe_provider` assignment at 99 to 101;
  `extra={` at 104; `"provider": safe_provider` at 105; `"provider": provider` persisted in the item
  at 87; `safe_provider_validated` at 253; `extra={"provider": ...}` at 258. All verified against the
  260-line file.
- **`plan.md` line 21 carries no template seed.** The banned term in
  `.specify/templates/plan-template.md` placeholder text is absent from this plan, and the whole
  feature directory greps clean for all seven banned terms.
- **No success criterion keys on an alert number.** SC-001 through SC-007 all key on path plus rule
  id, on the merged file, or on the test suite. The gate table's rows are written so that a respawned
  number classifies Refuted. This check initially passed on the SC list alone and **missed X10**,
  which was in an Independent Test line rather than in an SC; the sweep was redone across acceptance
  scenarios and independent tests as well, which is where it was caught.
- **`plan.md` line 21 carries no template placeholder.** Separately confirmed that
  `scripts/check-banned-terms.sh` excludes `./.specify/` (line 42), so the seeded term in
  `plan-template.md` is never scanned at source. The only real exposure is a placeholder copied into
  a feature's own plan, which is what happened at `specs/1268-cors-404-headers/plan.md:21` and did
  not happen here.

### D-bis. Mid-review correction applied

The coordinator corrected one premise this review had been given, verified against the live API by a
sibling reviewer: **the code scanning alerts API exposes no function field.**
`most_recent_instance.location` carries `path`, `start_line`, `end_line`, `start_column` and
`end_column`. Function-level keying is therefore not mechanically achievable, and deriving a function
from a `start_line` smuggles the line instability back into the criterion. The correct standard is
**path plus rule id**.

This review had initially "fixed" X3 in the wrong direction, re-scoping SC-001 from path to
path-plus-function to match the gate. That edit was reverted and the gate was moved to path plus rule
id instead, which is what SC-001 said all along and what the inherited convention §3 Trap 2 already
required. Recorded rather than quietly amended, because the wrong fix was live in the artifacts for
part of this session and the reversal is the substantive event.

Worth stating plainly: the contradiction X3 identified was real and the finding stands. Only the
resolution moved. The function boundary keeps a genuine but smaller job, deciding who owns a
survivor, which is now FR-006a.
- **The convention document exists and every cited section is real.**
  `specs/001-ingestion-arn-logging/codeql-logging-convention.md` is present, and §1's closing
  paragraph (lines 43 to 45), §2, §3, §4 and §5 all carry the content cited against them.
- **`BLOCKED-ON-OWNER` triggering on a failed `PATCH` is not the anti-pattern the sibling forbids.**
  Sibling FR-008a bans determining permission by *attempting a dismissal*, because a successful one
  cannot be undone. Step 4b is the intended dismissal, not a probe, so a permission failure there is
  an observation rather than a mutation. No finding.

### E. Counts and gate

**5 HIGH and 1 MEDIUM of drift (section A), 5 HIGH plus 1 MEDIUM plus 4 LOW of cross-artifact
inconsistency (section B), 1 HIGH cross-feature conflict (section C).**

Totals: **0 CRITICAL, 11 HIGH, 2 MEDIUM, 4 LOW.** All CRITICAL and HIGH findings are fixed in place,
plus the two MEDIUMs that were single-edit repairs (D6, X5). The four LOWs are recorded and left.

Two of the eleven HIGHs (X3 and X10) arrived through coordinator propagation from sibling reviewers
rather than from this review's own sweep, and one of those (X3) had already been "fixed" here in the
wrong direction before the correction landed. Both are recorded at full severity with the correction
history intact rather than folded in silently, because the review-technique lesson is the more
transferable finding: **check the source spec last and independently, not by reading outward from it.
A derived artifact that obeys a rule is weak evidence that the source does.**

**GATE: 0 CRITICAL, 0 HIGH remaining.**
