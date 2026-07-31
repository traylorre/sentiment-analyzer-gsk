# Feature Specification: Close CodeQL alert 144 (OAuth provider taint)

**Feature Branch**: `001-oauth-provider-taint`
**Created**: 2026-07-30
**Status**: Draft (revised after Adversarial Review #1, Adversarial Review #2, and the Stage 7
cross-artifact analysis in [tasks.md](tasks.md))
**Input**: User description: "Resolve CodeQL alert 144 (`py/clear-text-logging-sensitive-data`) at `src/lambdas/shared/auth/oauth_state.py:104`."

## Context

CodeQL alert 144 is open on `refs/heads/main` with severity `high`. The reported sink is the
`extra={...}` dict literal in `store_oauth_state()`, spanning lines 104 to 108 of
`src/lambdas/shared/auth/oauth_state.py`. The alert message is "This expression logs sensitive
data (password) as clear text."

The only non-constant value entering that dict is `safe_provider`, derived from the function's
`provider` parameter. In production `provider` is never request-derived: the two production call
sites pass string literals (`"google"` and `"github"`). No secret, token, credential, or user
input reaches this expression.

### The `extra` dict is never rendered

`oauth_state.py` uses the standard library logger (`logging.getLogger(__name__)`). No handler or
formatter in this repository renders `extra` keys: `src/lambdas/shared/logging_config.py` is
documented and implemented as a level-setter only, and it "never attaches handlers or formatters".
The root handler is the runtime's default, which formats `record.getMessage()` and nothing else.

Captured production log output confirms this. The post-deploy evidence in
`specs/001-lambda-log-visibility/evidence/post-deploy/logshape-dashboard.json` records three real
emissions of this exact call on 2026-07-27, and every one is bare:

```text
[INFO]	2026-07-27T16:54:55.291Z	ccc0f079-351f-464c-85ec-7082529fbe36	OAuth state stored
```

No `provider`, no `has_user_id`, no `ttl_seconds`. **The logs do not today distinguish a Google
authorize from a GitHub authorize, and never have on this line.** Any requirement to preserve that
distinction would be protecting a capability that does not exist. This is why the remedy below is
a straight deletion rather than a substitution, and why the deletion costs nothing operationally.

Independently: no metric filter, alarm, dashboard, or runbook consumes this line. The repository's
only log metric filter is `dashboard_import_errors`
(`infrastructure/terraform/modules/monitoring/main.tf:30`). And `provider` is persisted regardless,
at `oauth_state.py:87`, inside the item written by `put_item`.

### Prior art: transformation fails, removal works

Two things are established and must not be re-litigated. Inline CRLF sanitization was already tried
on this exact line by `8424cbd` (2026-01-20). It did not merely fail: it **relocated** the finding,
closing alert 117 at line 95 and opening alert 144 at line 104 in the same analysis run (see "This
file has already produced a respawn" below). That is worse than no progress, because it produced
the appearance of a fix while the reported disclosure survived nine lines away. CRLF stripping
addresses `py/log-injection`, a different rule. And sanitization cannot work here in principle: in
the analyzer's Python dataflow model `str(x).replace(...)` and slicing propagate taint rather than
removing it, as the repo's own `sanitize_for_log()` docstring states.

The remediation that does work is on record, with alert-state evidence anchored on commit SHAs
rather than dates.

- **`0e7a375` (PR #321, merged 2025-12-09 21:40:15Z)** routed the sensitive value through an
  intermediate variable before logging it. It failed instructively: alerts **110 and 111** were
  created at 2025-12-09T21:38:16Z and are both pinned by the API to commit
  `0e7a3752aaba49c502d0403a11544965911b8262`, at the lines that commit had just rewritten
  (`secrets.py:230` and `:243`).
- **`ebcc2f4` (PR #322, merged 2025-12-09 22:18:14Z)** superseded it and worked. Its commit message
  states the finding directly: the analyzer "traces taint through function calls, so intermediate
  variables still trigger alerts. The only solution is to avoid using ANY value derived from
  `secret_id` in the `logger.info()` extra context." Alerts 110 and 111 both carry
  `fixed_at = 2025-12-09T22:19:20Z`.

The `fixed_at` field makes the split causal rather than circumstantial:

| Site shape | Alerts | `fixed_at` |
|---|---|---|
| Derived value removed from `extra` (`ebcc2f4`) | 26, 27, 106, 107, 110, 111 | all set |
| Sanitizer call left inside `extra` (`secrets.py:171, 186, 198, 210`) | 22, 23, 24, 25 | **null to this day**, 8 months on |

Alerts 26 and 27 still read `dismissed` only because dismissal is sticky and predates the fix by
two weeks; they carry `fixed_at` values as well. The four sites that kept a sanitizer call inside
`extra` were never fixed, only annotated.

### This file has already produced a respawn

The decisive precedent is in this very file, and it is exact rather than same-day:

| Alert | Path:line | Created | Fixed |
|---|---|---|---|
| 117 | `oauth_state.py:95` | 2026-01-10T19:25:14Z | **2026-01-20T22:34:56Z** |
| 144 | `oauth_state.py:104` | **2026-01-20T22:34:56Z** | null |

The same analysis run closed 117 and opened 144, nine lines further down, for the same rule in the
same function. `8424cbd` did not fix this finding; it moved it. A disappearing alert number is not
evidence of a fixed sink, and the replacement can land well outside any narrow line window drawn
around the old sink.

**What is still genuinely unknown:** why the engine classifies this value as "password". The REST
API returns no `code_flows` for alert 144, so the taint path cannot be inspected. This
specification makes no claim about the cause and no requirement depends on discovering it. The
prior art raises confidence in the remedy; it does not explain the diagnosis.

### What a CodeQL result is worth here

CodeQL is not a required status check on this repository. The required contexts are exactly
`Secrets Scan`, `Lint`, `Run Tests`, and `Playwright E2E Tests`, and the rulesets API returns `[]`.
No CodeQL result blocks a merge today. The alert is worth closing because it is a standing open
high-severity finding on the default branch, not because it gates anything.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Apply the proven remediation shape (Priority: P1)

A maintainer removes the `provider` key from the log `extra` context of `store_oauth_state()`
entirely, which is the exact shape that closed this rule in `ebcc2f4`. The maintainer then reads
the alert state from the default-branch analysis to confirm the outcome.

**Why this priority**: A real code fix is strictly better than a dismissal: it removes the finding
rather than annotating it, and leaves no standing exception. The repo has already demonstrated that
this precise shape works for this rule, so it must be attempted before any dismissal.

**Independent Test**: Apply the change, let the default-branch analysis run, then query the alert
state. This alone resolves the feature if the alert closes, and produces the decisive evidence for
the fallback branch if it does not.

**Acceptance Scenarios**:

1. **Given** no value derived from `provider` appears in the `extra` context, **When** the
   default-branch analysis completes, **Then** the maintainer can classify the outcome against the
   decision gate without ambiguity.
2. **Given** the change is applied, **When** the existing OAuth unit tests run, **Then** they pass
   without modification to their assertions about stored state or returned values.

#### Why deletion, and not a substituted literal

An earlier draft proposed logging a genuine literal selected by an allowlist membership check, to
keep a provider distinction while no derived string reached the sink. It is dropped because it
preserves nothing (`extra` is not rendered, so there is no distinction to keep) and because it is
unproven at a cost. `ebcc2f4` proved that *removing* a derived value closes the rule; it did not
prove that *a literal selected by branching on the tainted value* counts as removal, and if the
analyzer models implicit or control-flow taint here, that form still flags. Trying it first means
editing this sink twice, and the 117-to-144 record above shows what a second edit costs.

One honest caveat about the precedent: `ebcc2f4` did not delete information outright, it relocated
the sanitized identifier into a raised exception message, a sink the analyzer tolerates.
`store_oauth_state()` has no raise on its path at all (it is `put_item`, log, return), so there is
no equivalent relocation target here, making this deletion strictly more aggressive than the
precedent. Given that the value is not rendered anyway and remains persisted at line 87, that
difference costs nothing.

---

### User Story 2 - Fall back to a justified dismissal (Priority: P2)

If removing the value does not close the alert, the maintainer dismisses it as a false positive
with a written justification, following the convention settled by `001-ingestion-arn-logging`. This
is the contingency branch, reached only after the proven code shape is refuted. Given the `ebcc2f4`
precedent it is unlikely, but it is what guarantees the alert count reaches zero either way.

**Independent Test**: With the dismissal applied, query the alert-state API and confirm that
`src/lambdas/shared/auth/oauth_state.py` carries **zero open findings** for
`py/clear-text-logging-sensitive-data`, and that whichever alert number was actually observed at the
sink reports `dismissed` with a non-empty justification matching the convention. The test is keyed on
the path plus the rule id, never on alert 144 reaching a state: 144 is a locating label for the
finding as it stood at authoring time, and `8424cbd` already demonstrated on this exact file that the
number carrying a finding can change between analyses while the finding survives. A test written as
"144 is dismissed" would fail on a correctly handled respawn and pass on an unhandled one.

**Acceptance Scenarios**:

1. **Given** the code fix left an open finding at the sink, **When** the maintainer dismisses it,
   **Then** the dismissal reason is "false positive" and the recorded comment names the value
   logged, the convention applied, and why the analyzer still reports the flow.
2. **Given** the code fix has not been applied and evaluated, **When** the maintainer reaches the
   dismissal step, **Then** the step is blocked. A proven remedy must be exhausted first.

---

### User Story 3 - Prevent the failed approach from being retried (Priority: P3)

Pure durability value. The alert closes without it, but without it the same dead end costs someone
else a cycle, as it already has twice: `0e7a375` in December and `8424cbd` in January, the second
apparently unaware of the first.

**Acceptance Scenarios**:

1. A reader of the feature's artifacts can state, without reading commit history, which approaches
   were tried, which one worked, and how that was verified.
2. A reader who has only the source file in front of them, and none of these artifacts, is warned at
   the sink itself that the key was removed for this rule, and is pointed at where the reasoning
   lives. Artifacts alone do not satisfy this story: the failure mode is a later refactor
   reintroducing the key, and whoever writes that refactor is looking at the file, not at
   `specs/`. See FR-013.

---

### Edge Cases

- **The analysis does not re-run, or reports a stale result.** A result predating the change decides
  nothing. See the decision gate for the bound on that wait.
- **Alert 144 closes but a new finding of the same rule appears on the path.** Refuted, not success,
  and exactly what `8424cbd` produced. Success is
  `src/lambdas/shared/auth/oauth_state.py` being free of open findings for
  `py/clear-text-logging-sensitive-data`, not one alert number disappearing. The criterion is **path
  plus rule id**, matching FR-006 and SC-001: the alerts API exposes no function field, so a
  function-scoped reading of this bullet would key on a value derived from a `start_line` and would
  smuggle back the line instability the gate exists to avoid. Attribution to a function still happens
  on a survivor, per FR-006a, but only to decide who owns it.
- **A survivor attributes outside `store_oauth_state()`.** Not Confirmed, and not this feature's to
  dismiss. It is reported per FR-006a, and the feature terminates in that reported state.
  `validate_oauth_state()` is frozen by FR-004.
- **The change is complete and green but has not landed on the default branch.** No qualifying
  analysis can exist yet, so the gate is not evaluated at all. This is `PENDING-BRANCH-ANALYSIS`,
  inherited whole from `specs/001-ingestion-arn-logging/codeql-logging-convention.md` §5a, which
  calls it "the normal ending, not an edge case". It is distinct from the 7-day
  `BLOCKED-NO-ANALYSIS` bound below, which starts only once the change is on `main`.
- **Both branches fail.** The feature reports the blockage rather than suppressing the rule or
  lowering its severity.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: No value derived from the `provider` parameter by transformation, slicing,
  formatting, replacement, or an intervening helper call MAY appear in the log `extra` context of
  `store_oauth_state()`. This is the property `ebcc2f4` established as the remedy for this rule.
- **FR-002**: FR-001 MUST be satisfied by removing the `provider` key from the `extra` context
  entirely, which is the exact `ebcc2f4` shape. A substituted or allowlist-selected value MUST NOT
  be used, because `extra` is not rendered and such a substitution would preserve nothing while
  requiring an unproven second rewrite of the sink.
- **FR-003**: The runtime behavior of `store_oauth_state()` outside the log call MUST be unchanged.
  The stored item (including the persisted `provider` at line 87), the returned object, and the
  generated PKCE verifier are untouched.
- **FR-004**: `validate_oauth_state()` MUST NOT be modified by this feature. Its `provider` value
  is request-derived, which makes it a materially different case, and it is not this alert's sink.
- **FR-005**: The outcome MUST be classified against the decision gate below, defined before the
  change is applied, with each observation mapping to exactly one follow-on action.
- **FR-006**: Confirmed MUST require that `src/lambdas/shared/auth/oauth_state.py` carries no open
  finding for `py/clear-text-logging-sensitive-data` in a completed default-branch analysis of a
  commit containing the change. The criterion is path plus rule id, matching SC-001 and the inherited
  convention §3. An open finding anywhere in that file blocks Confirmed, including one outside
  `store_oauth_state()`: the API exposes no function field, so any function attribution is derived
  and MUST NOT be what licenses a Confirmed result. Attribution is still performed, but only to
  decide how a survivor is handled (FR-006a), never to declare success while one is open.
- **FR-006a**: A survivor MUST be attributed before it is acted on. If it maps inside
  `store_oauth_state()`, it is this feature's, and FR-007's dismissal path applies. If it maps
  elsewhere in the file, in particular to the `validate_oauth_state()` sink at lines 253 to 258 that
  FR-004 freezes, it is NOT this feature's to dismiss: it MUST be reported to the repository owner
  as a finding needing its own owner, and the feature terminates in that reported state rather than
  in Confirmed. Attribution is a derived, best-effort mapping and is recorded as such.
- **FR-007**: Only after the FR-002 change is applied and refuted at the gate MAY the alert be
  dismissed as a false positive, with a written justification naming the value logged, the
  convention applied, and why the analyzer still reports the flow despite no derived value reaching
  the sink. A dismissal is a security shortcut under constitution §9, so recording one MUST also
  add an entry to the tech debt registry at `docs/reference/TECH_DEBT_REGISTRY.md` carrying the
  fields §9 requires (ID, Location, Status, Root Cause, Proposed Fix, Effort, Risk). No registry
  entry is created on the confirmed branch, where a closed finding creates no debt.
- **FR-008**: This feature MUST consume the convention recorded at
  `specs/001-ingestion-arn-logging/codeql-logging-convention.md` in full, not only its dismissal
  wording. That document was written under the sibling's FR-011 to be cited by this feature, and
  consuming it whole is what keeps the following from being independently redefined here: the
  dismissal wording pattern and its three required elements (§2), the `fixed_at` versus `state` and
  alert-number-instability caveats (§3), the blast radius prohibition on editing
  `src/lambdas/shared/secrets.py` (§4), and **both** terminal states §5 defines:
  `PENDING-BRANCH-ANALYSIS` for the case where the change is complete but no default-branch analysis
  of it can exist yet (§5a), and `BLOCKED-ON-OWNER`, with its handoff artifact contents, for the case
  where the implementing agent lacks permission to dismiss (§5b). Consuming §5 whole means consuming
  both: §5a is the state the convention itself calls "the normal ending, not an edge case", and
  omitting it leaves an implementing agent whose change has not yet landed with no terminal state to
  record, which is an implicit abort. §5b also fixes **how** the dismissal permission is
  established: by a read-only probe of the token's scopes together with the repository's visibility
  and the actor's repository permissions, **never** by attempting a dismissal, because a successful
  one cannot be cleanly reverted. A missing `security_events` scope is not by itself a blocker; that
  scope is a private-repository requirement, and on a public repository `repo` subsumes what the
  endpoint needs.
  This feature MUST NOT define a second convention for any of them, and where its own artifacts
  restate one they MUST cite that document's section rather than a sibling requirement number.
- **FR-009**: Alert closure MUST be evidenced from default-branch analysis state or the alert-state
  API. A green pull request check MUST NOT be accepted as evidence of closure.
- **FR-010**: The feature MUST NOT suppress the rule repo-wide, lower its severity, exclude the
  file from analysis, or add an inline suppression comment as a substitute for FR-007.
- **FR-011**: The existing OAuth unit tests MUST pass without modification to their assertions
  about stored state or returned values.
- **FR-012**: The record of prior art MUST state that `8424cbd` *relocated* this finding rather
  than failing to clear it, naming alert 117 (line 95, `fixed_at` 2026-01-20T22:34:56Z) and alert
  144 (line 104, `created_at` the same timestamp); state that the rule it addressed was log
  injection rather than clear-text logging; and cite `0e7a375` (failed, intermediate variable,
  spawned alerts 110 and 111) and `ebcc2f4` (succeeded, value removed from log context) as the
  in-repo precedent for what does and does not close this rule.
- **FR-013**: The log call in `store_oauth_state()` MUST carry an inline comment naming the rule id
  `py/clear-text-logging-sensitive-data` and stating why no `provider`-derived value may be added to
  the `extra` context, on every branch of the decision gate including the confirmed one. This is the
  unconditional site-comment clause of the inherited convention (§1, closing paragraph), consumed
  via FR-008, and it is what carries US3's durability into the code rather than leaving it only in
  this directory. The comment is documentation and MUST NOT carry `# nosec`, `# noqa`, `# lgtm`, or
  any CodeQL suppression pragma; so constrained it is not the inline suppression comment FR-010
  forbids, because it suppresses nothing and substitutes for no part of FR-007.

### Decision Gate

The gate is evaluated once, against one completed default-branch analysis of a commit that contains
the FR-002 change.

**Scope of the gate.** The gate is anchored on **path plus rule id**: any open
`py/clear-text-logging-sensitive-data` finding on `src/lambdas/shared/auth/oauth_state.py`. Never on
an alert number, and never on a line number or a window around one. Alert numbers are not identity,
because `8424cbd` closed alert 117 at line 95 and opened alert 144 at line 104 at the identical
timestamp. Line numbers are not identity either, because this feature edits the file and shifts every
line below the sink. Function is not used as the criterion because the alerts API exposes no function
field: `most_recent_instance.location` carries only `path` and line and column bounds, so any
function attribution is derived from a `start_line` and inherits precisely the line instability the
gate exists to avoid. Attribution to a function is still performed on a survivor, per FR-006a, but it
decides *who owns the survivor*, never whether the gate passed.

| Observation | Classification | Required follow-on |
|---|---|---|
| No open `py/clear-text-logging-sensitive-data` finding on `oauth_state.py` | Confirmed | Stop. Record the result. No dismissal. |
| Alert 144 still open on the path, attributed to `store_oauth_state()` | Refuted | Proceed to dismissal per FR-007 and FR-008. |
| Alert 144 closed but a new finding of the same rule is open on the path, attributed to `store_oauth_state()` | Refuted | Proceed to dismissal per FR-007 and FR-008, dismissing the new alert number and recording that a respawn occurred. |
| A finding of this rule is open on the path but attributes outside `store_oauth_state()` | Not Confirmed, and not this feature's to dismiss | Report to the repository owner per FR-006a. Terminal and reported. Do not dismiss it here; `validate_oauth_state()` is frozen by FR-004. |
| The change is complete and green but has not landed on the default branch | Not evaluable yet, and not blocked | Terminal state `PENDING-BRANCH-ANALYSIS` (below). Neither done nor failed. |
| The change has landed, but no completed default-branch analysis covers it yet | Not yet decidable | Wait, bounded (below). |

**The change has not landed yet.** Closure is read from a default-branch analysis (FR-009), and no
such analysis can exist while the change sits on a feature branch, so the gate is not evaluated at
all rather than evaluated and failed. The feature MUST terminate in `PENDING-BRANCH-ANALYSIS`,
recording the code change as complete and green and writing the gate query, filled in with this
feature's own path and rule id, so the check is mechanical the moment the change lands. This state is
inherited whole from `specs/001-ingestion-arn-logging/codeql-logging-convention.md` §5a via FR-008,
which calls it "the normal ending, not an edge case", and it MUST NOT be reported as done or as
failed. It is not the same state as the bound below: this one is entered before the change reaches
`main`, and the 7-day clock has not started.

**Bounding the wait.** The "not yet decidable" state MUST NOT persist unbounded. If no completed
default-branch analysis covering the change is available within 7 days of the change landing on the
default branch, the feature MUST be reported as blocked to the repository owner, naming the missing
analysis, rather than left open. It MUST NOT be classified, and it MUST NOT be dismissed. Blocked
is a terminal reportable state; it is not a third attempt.

The change is retained on the refuted branch as well. It is a defensible improvement on its own
terms, and reverting it would restore a derived-string log for no benefit.

## Success Criteria *(mandatory)*

- **SC-001**: Querying the alert-state API shows zero open `py/clear-text-logging-sensitive-data`
  findings against `src/lambdas/shared/auth/oauth_state.py`, in either the fixed or dismissed state.
  The scope is **path plus rule id**, which is the strongest identity the API mechanically supports:
  `most_recent_instance.location` carries `path`, `start_line`, `end_line`, `start_column` and
  `end_column`, and no function field. It is also the formulation the inherited convention settled on
  (`specs/001-ingestion-arn-logging/codeql-logging-convention.md` §3, Trap 2: "Zero open alerts of
  this rule at this path"). Function-level scoping is deliberately NOT used as the criterion, because
  deriving a function from a `start_line` reintroduces exactly the line-number instability the
  criterion exists to dodge.
- **SC-002**: The evidence cited for SC-001 comes from default-branch analysis state or the
  alert-state API. No pull request check result is cited as closure evidence.
- **SC-003**: This feature's diff introduces no new open code scanning alert anywhere in the
  repository. The test is attribution, not a repo-wide count: every open alert present after the
  change is either one of the five observed at authoring time (144, 147, 148, 149, 150) or is
  attributable, by path, to a change this feature did not make. A repo-wide count MUST NOT be used
  as the criterion, for two reasons. Sibling `001-codeql-coverage` enables an additional analysis
  leg and states plainly that the open count "will very likely RAISE" (`specs/001-codeql-coverage/spec.md:15`,
  and its own SC-004 refuses to fail on a rise); and the owner's directive governing this campaign is
  that coverage is the goal, not a low alert count. Keying this feature's success on a global counter
  would fail it for a sibling doing exactly what it was asked to do. The condition that remains
  binding, and is wholly within this feature's control, is keyed on paths rather than on a count: no
  alert of any rule newly appears on `src/lambdas/shared/auth/oauth_state.py` or on
  `src/lambdas/shared/secrets.py`.
- **SC-004**: The existing OAuth state unit test suites pass with no assertion changes.
- **SC-005**: The decision gate resolves to exactly one classification, and the artifacts state
  which branch was taken and on what observed evidence.
- **SC-006**: If the dismissal branch is taken, the recorded justification is non-empty, matches the
  convention adopted from `001-ingestion-arn-logging`, and the artifacts show the FR-002 change was
  applied and refuted before the dismissal was recorded. A corresponding entry exists in
  `docs/reference/TECH_DEBT_REGISTRY.md` carrying every field constitution §9 requires.
- **SC-007**: The log call in `store_oauth_state()` carries the FR-013 comment, on whichever branch
  the gate selected, and that comment contains no suppression pragma. Verifiable by inspecting the
  merged file.

## Dependencies

- **`001-ingestion-arn-logging` (convention settled)**: Owns the dismissal convention, which this
  feature consumes rather than redefining: attempt the real fix first using the
  no-derived-value-in-log-context shape, and treat dismissal as a fallback carrying a written
  justification. FR-001, FR-007 and FR-008 are this feature's expression of it.
- **File disjointness**: confirmed. The sibling covers `src/lambdas/ingestion/handler.py` (alerts
  148, 149, 150); this one covers `src/lambdas/shared/auth/oauth_state.py` (alert 144). No shared
  files, so the two may complete in either order.

## Assumptions

- The default-branch analysis runs on merge and produces a fresh alert state within a normal
  turnaround. The 7-day bound in the decision gate covers the case where it does not.
- Dismissing a code scanning alert requires write access to code scanning alerts. On a **private**
  repository that means the `security_events` scope; on a **public** one, which this is,
  `public_repo` suffices and the `repo` scope subsumes it (convention §5b). A missing
  `security_events` scope is therefore **not** by itself a blocker, and reading `gh auth status`
  alone and concluding otherwise is the specific mistake §5b exists to prevent. Seven prior
  dismissals of this rule exist here (alerts 1 and 22 through 27), so the precedent is established
  and some actor holds the permission. It is **not** assumed that the implementing agent does; that
  is settled by the read-only probe, never by attempting a dismissal. If the probe resolves to
  *absent*, the
  dismissal branch terminates in `BLOCKED-ON-OWNER` with a handoff artifact, inherited via FR-008
  from `specs/001-ingestion-arn-logging/codeql-logging-convention.md` §5. That is a reported terminal
  state, neither done nor failed.
- The production call sites remain the only production callers passing `provider`. If a future
  change makes it request-derived here, that is a new assessment, not a regression of this one.
  Removing the value from the log context is safe under either provenance, which is a further
  argument for FR-002 over a substituted literal.
- No consumer of the `extra` dict is introduced concurrently. If a structured-JSON formatter were
  attached to the root handler later, the provider distinction would still be absent from this
  line, and restoring it would be a new feature with its own analysis of this rule.

## Out of Scope

- The request-derived `provider` in `validate_oauth_state()`. Different function, different data
  provenance, not this alert's sink.
- The other four open alerts (148, 149, 150 in `src/lambdas/ingestion/handler.py`; 147
  `py/bad-tag-filter` in `scripts/regenerate-mermaid-url.py`). Each is owned by its own feature.
- Changing `sanitize_for_log()`, `logging_config.py`, or any other shared logging helper. Making
  `extra` render is a separate concern with its own blast radius.
- The inline CRLF sanitization applied elsewhere in `oauth_state.py`. It is still doing its job for
  the log injection rule.
- Revisiting the seven existing dismissals of this rule, or any change to analysis configuration,
  rule severity, query packs, or scan scheduling.
- New infrastructure of any kind.

---

## Adversarial Review #1

Reviewer did not author this spec. All API claims below were re-derived independently against the
GitHub code scanning API, not taken from the prior draft.

### Findings

| Severity | Finding | Resolution |
|---|---|---|
| CRITICAL | **FR-002 (old) protected a capability that does not exist.** `oauth_state.py` uses `logging.getLogger(__name__)`; `logging_config.py` is a level-setter that by its own docstring "never attaches handlers or formatters"; the root handler is the runtime default, which renders `record.getMessage()` only. Captured production output in `specs/001-lambda-log-visibility/evidence/post-deploy/logshape-dashboard.json` shows three real emissions of this call on 2026-07-27, all bare: `OAuth state stored`, with no `provider`, `has_user_id`, or `ttl_seconds`. The logs have never distinguished Google from GitHub on this line. | FIXED. Old FR-002 and FR-003 deleted, along with SC-004 (the allowlist unit test) and the "unknown provider fallback" edge case. New Context section documents the non-rendering with the evidence path. |
| CRITICAL | **Form A's sole rationale was the void FR-002.** With nothing to preserve, the allowlist-literal form is an unproven speculative attempt whose only effect is to edit this sink twice, on a sink with a documented respawn history. | FIXED. Form A, FR-001a, FR-001b, the two-form table and the per-form gate re-evaluation are all removed. The proven `ebcc2f4` shape is now the first and only code attempt (new FR-002). The owner's principle, that a proven in-repo fix must be exhausted before dismissal, is preserved and strengthened: the proven fix is now attempt one, not attempt two. |
| HIGH | **False precedent claim.** The draft stated `0e7a375` raised alerts 107, 110 and 111. Alert 107 is pinned by the API to commit `a245d1d9` and was created 2025-12-09T08:47:23Z, roughly 13 hours *before* `0e7a375` was committed (21:40:15Z). Only 110 and 111 carry `0e7a375`'s SHA. | FIXED. Corrected to 110 and 111, and re-anchored on the `most_recent_instance.commit_sha` field rather than on the calendar date, which was the source of the error. |
| HIGH | **The strongest available evidence was absent.** Alert 117 (`oauth_state.py:95`) has `fixed_at = 2026-01-20T22:34:56Z`; alert 144 (`oauth_state.py:104`) has `created_at =` the identical timestamp. One analysis run closed one finding in this function and opened this one nine lines down. Decision Gate row 3 is not a hypothetical borrowed from another file; it already happened here. | FIXED. Promoted to its own subsection, "This file has already produced a respawn", and cited directly in the gate's scoping paragraph. |
| CRITICAL | **Line-number adjacency was self-invalidating and already provably wrong.** Escalated from HIGH once the 117-to-144 respawn was confirmed. The draft's "adjacent = lines 99 to 109 at authoring time" would have *missed the very precedent it was written to catch*: the historical respawn moved a finding from line 95 to line 104, and 95 falls outside 99-109. The feature also edits this file, shifting every line number in it. | FIXED. The gate is scoped to the body of the function `store_oauth_state()` plus the rule id, with an explicit note that line numbers are deliberately not used and why. The assumption defining "adjacent" as 99-109 is deleted. |
| HIGH | **`8424cbd`'s history was mischaracterized as "the alert did not clear."** It did clear one: the run closed alert 117 and opened alert 144. Saying it "failed" invites the reader to conclude sanitization does nothing, when it did something worse, producing the appearance of progress while the disclosure survived nine lines down. | FIXED in both the prior-art paragraph and FR-012, which now requires the record to say "relocated", with both alert numbers and the shared timestamp. |
| HIGH | **The gate did not terminate.** "Not yet decidable, wait" had no owner, no bound, and no alternative action, so the feature could sit indefinitely in a state that was neither done nor advancing. | FIXED. Added a 7-day bound from the change landing on the default branch, after which the feature is reported blocked to the repository owner. Blocked is stated as terminal and reportable, explicitly not a further attempt. |
| MEDIUM | **CodeQL-based success criteria are weaker than they read.** CodeQL is not a required status check; required contexts are exactly `Secrets Scan`, `Lint`, `Run Tests`, `Playwright E2E Tests`, and the rulesets API returns `[]`. No CodeQL result blocks a merge. | RECORDED, with a short "What a CodeQL result is worth here" subsection added so the criteria are not read as gating. Not treated as a defect: the finding is a real open high-severity alert on the default branch regardless of what gates on it. |
| MEDIUM | **No consolation sink, understated.** `ebcc2f4` relocated its sanitized identifier into a raised exception message. `store_oauth_state()` is `put_item`, log, return, with no raise anywhere on its path, so the deletion here is strictly more aggressive than the precedent it cites. | FIXED. Stated plainly in "Why deletion, and not a substituted literal", together with why it costs nothing given the non-rendering finding and the persistence at line 87. |
| MEDIUM | **Over-specified.** 316 lines of spec for a one-line deletion, much of it structure serving a form that has now been removed. | FIXED by cutting. Removed: the form-comparison table, FR-001a/FR-001b, old FR-002/FR-003, the per-form gate language, SC-004, one edge case, two assumptions, and the "sequencing constraint discharged" bullet. Thirteen FRs became twelve; seven SCs became six. Net line count is flat (316 body lines to 315) because roughly 45 lines of removed speculative structure were traded for the same volume of hard evidence that was previously missing. Density is up; length is not. |
| LOW | **US3 spent 20 lines on one sentence of content.** | FIXED. Compressed to a single acceptance scenario. |
| LOW | **Two secrets.py line citations were wrong.** The draft listed the alert 22-25 sites as `171, 187, 199, 211`; the API reports `171, 186, 198, 210`. | FIXED in the prior-art table. |

Counts: **3 CRITICAL, 4 HIGH, 3 MEDIUM, 2 LOW.**

Note on the mid-review input from the coordinator: the 117-to-144 respawn had already been found
and folded in by this reviewer before that message arrived, via the same API queries. It is
confirmed, with one correction of detail: the gap is **nine** lines (95 to 104), not four. The
coordinator's third instruction, "make sure a literal-selecting allowlist that closes 144 and opens
151 is not scored as success", is satisfied by construction rather than by tightening the gate: the
allowlist form is removed entirely (CRITICAL 2), and the gate is anchored on the function plus the
rule id, so any replacement alert number in `store_oauth_state()` classifies as refuted.

### Independent API verification

Every claim below was re-derived by the reviewer via `gh api`, not inherited.

- Alert 144: `state=open`, `start_line=104`, `end_line=108`, severity `high`, ref `refs/heads/main`, `code_flows` length **0**. Confirmed; the spec correctly makes no claim about the taint path.
- `fixed_at` non-null for exactly 26, 27, 106, 107, 110, 111. Confirmed.
- `fixed_at` null for 22, 23, 24, 25, all `state=dismissed`, all in `secrets.py`. Confirmed.
- 26 and 27 are `dismissed` (2025-11-24) yet carry `fixed_at` (2025-12-03 and 2025-12-09). Confirmed; dismissal is sticky and predates the fix.
- Alerts 110 and 111 created 2025-12-09T21:38:16Z, both `commit_sha = 0e7a3752aaba49c502d0403a11544965911b8262`. Confirmed as `0e7a375`'s respawn.
- Alert 107 created 2025-12-09T08:47:23Z, `commit_sha = a245d1d9…`, 13 hours before `0e7a375`. **Refutes** the draft's attribution.
- Alert 117 `fixed_at` equals alert 144 `created_at` exactly (2026-01-20T22:34:56Z), same file, lines 95 and 104. New, and load-bearing.
- Seven dismissed alerts for `py/clear-text-logging-sensitive-data` (22-27 plus one other). Confirmed.
- Five open alerts repo-wide: 144, 147, 148, 149, 150. Baseline confirmed.

### Gate

**0 CRITICAL, 0 HIGH remaining.**

---

## Clarifications

### Session 2026-07-30

Four questions were raised. All four were self-answered from the repository, the GitHub API, or git
history; **none were deferred to the owner**. No fifth question was raised: after Adversarial Review
#1 and the planning pass, the remaining artifacts left no further genuine ambiguity, and manufacturing
one to fill a quota would have been noise. Two of the four changed requirements; the other two closed
as verifications.

Every answer below cites evidence that was re-derived at clarification time rather than inherited
from the prior artifacts.

---

#### Q1. Does the inline comment at the sink belong in the spec as a requirement, or does it stay a plan-level implementation choice?

**Answer: it belongs in the spec, and it is now FR-013.** Two independent reasons, and the first is
decisive.

The inherited convention already mandates it, unconditionally. The closing paragraph of §1 of
`specs/001-ingestion-arn-logging/codeql-logging-convention.md` (lines 43 to 46) reads:

> **Always**, whichever branch you land on: leave an inline comment at the site naming the rule id
> and the reason the value was removed. Unconditionally, including on sites where the fix worked
> cleanly. Without it, a later refactor reintroduces the interpolation and nothing objects.

That is not incidental wording. The sibling's own adversarial review raised it as a MEDIUM finding
and escalated the requirement for exactly this failure mode (`specs/001-ingestion-arn-logging/spec.md:149`:
"No regression guard on the success path. FR-010 required the inline comment only on sites behind a
dismissed alert, so if the fix worked cleanly all three sites would end unmarked and a later refactor
could reintroduce the interpolation silently. Fixed. FR-010 made unconditional across all three
sites."). Sibling FR-010 (`spec.md:92`) is the resulting unconditional requirement.

**Why the obligation was not already flowing through, which is the real defect this question
found.** FR-008 as written before this session bound only "the dismissal justification's wording and
recording location" to the sibling. The comment clause is in neither the wording nor the recording
location of a dismissal, so it fell outside the inheritance and survived only as a plan choice. An
implementer reading spec.md alone had no requirement to write the comment, and one reading plan.md
could reasonably drop it as stylistic. Q3 found the identical break on a different clause, and both
are fixed by the same widening of FR-008.

**On the FR-010 tension, which is real and now explicit.** This feature's FR-010 forbids "an inline
suppression comment as a substitute for FR-007". Left unaddressed, FR-013 and FR-010 read as
contradictory to anyone who does not already know the distinction. FR-013 therefore states the
disjointness in its own text rather than relying on the reader: the comment is documentation, it
carries no `# nosec`, `# noqa`, `# lgtm` or CodeQL pragma, it suppresses nothing, and it substitutes
for no part of the dismissal path. The plan had already reasoned its way to this position
(`plan.md`, Implementation Design, property 3); the difference is that it is now binding and
verifiable rather than a choice recorded in a design note.

**Requirements changed**: new **FR-013**; **FR-008** widened (see Q3); **US3** gained a second
acceptance scenario, because the original one was satisfiable by the `specs/` directory alone while
the failure mode it exists to prevent is a refactor of the source file; new **SC-007** making the
comment verifiable on the merged file.

---

#### Q2. Constitution §9 requires a `docs/TECH_DEBT_REGISTRY.md` entry on the dismissal branch, but that file does not exist. Resolve or escalate.

**Answer: resolve. The registry exists; the path in the constitution is stale, and plan.md and
quickstart.md inherited the stale path from it.** No escalation is needed, and the §9 obligation is
live and satisfiable exactly as written apart from the path.

Evidence:

- `docs/TECH_DEBT_REGISTRY.md` does not exist. Confirmed.
- `docs/reference/TECH_DEBT_REGISTRY.md` does exist, carries 23 numbered entries (`TD-001` through
  `TD-023`), and is actively maintained. Its most recent commit is `cfa3202` (2026-07-30,
  "fix(toolchain): ruff 0.15.14 everywhere", PR #977).
- The file was originally created at `docs/TECH_DEBT_REGISTRY.md` on 2025-11-19 (`2a8746a`, "docs:
  Add tech debt registry and expand lessons learned") and was relocated by `f8db8d2`, "feat(docs):
  Reorganize documentation into categorical subdirectories" (PR #668).
- Constitution Amendment 1.4 is dated 2025-11-28, which is after the file was created and before it
  was moved. §9 was never updated to follow the move, which is why it names a path that has not
  existed since #668.
- §9's required fields and its allowed `Status` values (`Open | Resolved | Deferred | Blocked |
  Acceptable`) are unchanged and are met by the existing entries, so the `Status: Acceptable` value
  the plan intends for a dismissal is valid.

**Consequences applied.** FR-007 now carries the registry obligation explicitly, so it is a spec
requirement rather than something recorded only in plan.md's Constitution Check table. SC-006 now
requires the entry to exist on the dismissal branch. The path is corrected to
`docs/reference/TECH_DEBT_REGISTRY.md` in plan.md and quickstart.md.

**Superseded by Adversarial Review #2 on the identifier question.** This answer originally had
quickstart.md pre-reserve the next free id (**TD-024**, which is NOT reserved to this feature and
MUST NOT be taken from this document) "so the implementer does not have to derive it".
That was wrong: the registry is a shared file and three concurrent features were all reasoning from
the same `TD-023` high-water mark, so pre-reserving the id guaranteed a collision rather than saving
work. Sibling `001-ingestion-arn-logging` (`spec.md:249`) and sibling `001-codeql-coverage`
(`plan.md:282`) both already settled on merge-time allocation for exactly this reason. The rule is
now: **the identifier is read from the registry's then-highest entry at the moment the entry is
written, and is never pre-reserved in a spec.** The registry path stays corrected as above; only the
number is deferred.

**Carried forward, not fixed here.** Constitution §9's stale path is a defect in
`.specify/memory/constitution.md`, which is outside this feature's write scope and is shared with
three sibling agents. It is recorded for carding rather than folded into this feature. Note the
knock-on: §9's Acceptance Criteria clause "`docs/TECH_DEBT_REGISTRY.md` exists and follows the
documented format" is literally false today and has been since #668, so any future compliance check
reading §9 literally will fail on a path error rather than on a real gap.

**Requirements changed**: **FR-007** extended with the registry obligation and the correct path;
**SC-006** extended to require the entry.

---

#### Q3. Does the sibling actually define `BLOCKED-ON-OWNER` in a form this feature can cite, and does anything here silently duplicate it?

**Answer: yes, it is defined twice over and is citable. But the citation chain the plan used was
broken, and it is now repaired. Nothing duplicates it.**

The definition exists in two places, both usable:

- `specs/001-ingestion-arn-logging/spec.md:90`, FR-008a, which names the terminal state and requires
  a handoff artifact carrying "the exact alert numbers observed at the path, the exact dismissal
  justification text for each, and the exact API call or UI steps needed to apply them", and states
  that the code change is independently mergeable and that such a feature "MUST NOT be reported as
  done, and MUST NOT be reported as failed".
- `specs/001-ingestion-arn-logging/codeql-logging-convention.md` §5, lines 130 to 136, which carries
  the same content in a document whose header states it was "Written to be cited by
  `001-oauth-provider-taint`".

**The break.** plan.md and quickstart.md both cited it as "Inherited from sibling FR-008a via
FR-008". FR-008's scope was the dismissal justification's *wording and recording location*.
`BLOCKED-ON-OWNER` is a terminal state, not a wording and not a recording location, so FR-008 did
not reach FR-008a and the word "via" was doing work the requirement did not support. The same break
hid the §1 comment clause found in Q1. Quickstart also cited the three-element wording as sibling
"FR-009"; that number is correct (`spec.md:91`), but citing a sibling's requirement *number* is the
fragile form, since the sibling may renumber and this feature would not notice.

**The repair.** FR-008 is widened to consume the convention document in full and to require that
restatements cite that document's section rather than a sibling requirement number. The document is
the right anchor precisely because sibling FR-011 (`spec.md:93`) mandated its existence so that
"`001-oauth-provider-taint`, which works the same CodeQL rule, can cite it instead of inventing its
own". Citing the artifact the sibling was required to produce is stable; citing the numbering that
produced it is not.

**Duplication check: clean.** quickstart.md Step 4c restates the three handoff contents, but declares
them inherited rather than defined, and now cites §5. That is a restatement for operator
convenience, not a second convention. Nothing in this feature defines its own dismissal wording,
its own handoff contents, its own `fixed_at` caveat, or its own blast-radius rule. The one place
this feature does go beyond the sibling is the `BLOCKED-NO-ANALYSIS` and `BLOCKED-REGRESSION`
terminal states, which are genuinely this feature's own (the sibling has no decision gate and no
7-day analysis bound) and so are not duplications of anything.

**Requirements changed**: **FR-008** rewritten and widened.

---

#### Q4. Do the artifacts state clearly enough that the `safe_provider` assignment must be deleted rather than unwired, so an implementer cannot miss it?

**Answer: yes. Verified empirically and no change was needed.** This item closes as a confirmation.

The claim is true, and stronger than the artifacts asserted. Reproduced at clarification time by
copying `oauth_state.py`, deleting only the `"provider": safe_provider` entry, and running the
linter:

```text
F841 Local variable `safe_provider` is assigned to but never used
   --> probe.py:99:5
```

The line number matches the artifacts exactly: the assignment occupies lines 99 to 101 of
`src/lambdas/shared/auth/oauth_state.py`, as plan.md and quickstart.md both state. The rule is
active because `[tool.ruff.lint] select` in `pyproject.toml` includes `"F"` (pyflakes), and it
reaches CI because the `Lint` job runs `ruff check src/ tests/` at
`.github/workflows/pr-checks.yml:62`. `Lint` is one of the four required contexts, so an orphaned
assignment blocks the merge rather than merely producing a warning.

The artifacts state this in three places, at increasing specificity: plan.md's Constitution Check §8
row, plan.md's Implementation Design property 1 ("deleted, not orphaned"), and quickstart.md step 1a
("must be **deleted**, not left orphaned"). Two of the three name F841 and the required `Lint`
context by name. That is sufficient; no wording change was made, because adding a fourth statement of
the same point would dilute rather than clarify.

Worth recording alongside it: the deletion is also required on the merits independent of the linter.
FR-001 forbids any value derived from `provider` by replacement or slicing from reaching the context,
and leaving the derivation alive next to the sink is the exact shape `8424cbd` left behind. If F841
did not exist, the assignment would still have to go.

---

#### Verifications performed but not raised as questions

Recorded so a later reader knows these were checked rather than assumed.

- **SC-003's baseline still holds.** The open-alert set re-read at clarification time is exactly
  `{144, 147, 148, 149, 150}`, five alerts, and alert 144 is still `open` at
  `src/lambdas/shared/auth/oauth_state.py:104`. The baseline written at authoring time has not
  drifted.
- **The quickstart's regression test is implementable as written.** `store_oauth_state(table,
  state_id, provider, redirect_uri, user_id=None)` matches the snippet's four positional arguments;
  the module logger resolves to `src.lambdas.shared.auth.oauth_state`, which is the exact string the
  snippet passes to `caplog.at_level`; `logger.propagate` is `True`, without which `caplog` would
  capture nothing and the assertion would pass vacuously; and `OAUTH_STATE_TTL_SECONDS` is already
  imported at the top of `tests/unit/auth/test_oauth_state.py`, so no new production import is
  needed.
- **The test baseline is 30 passed**, as quickstart.md Step 0 states, so its "expect 31 passed"
  after the added method is right.
