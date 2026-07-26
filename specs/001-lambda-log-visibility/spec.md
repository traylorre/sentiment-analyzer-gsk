# Feature Specification: Lambda Log Visibility

**Feature Branch**: `001-lambda-log-visibility`
**Created**: 2026-07-26
**Status**: Draft
**Input**: User description: "Surface INFO-level application logs in CloudWatch across sentiment-analyzer Lambdas. All five preprod Lambdas have LoggingConfig LogFormat=Text with no ApplicationLogLevel, so the runtime attaches a root handler but never sets the root logger level; Python default WARNING applies and logger.info/debug from ~66 of 67 stdlib-logging modules under src/lambdas is silently dropped (WARNING+ was always visible). Three OAuth-incident bugs were debugged blind via X-Ray because the diagnostics were logger.info calls. Goal: INFO logs from all src/lambdas modules reach CloudWatch on dashboard, ingestion, analysis, notification Lambdas. SSE Lambda out of scope."

## Problem Statement

Application code across the backend emits informational diagnostics that never
reach the log system. The logging pipeline is configured so that only warnings
and errors survive; informational messages are silently discarded before they
are recorded. This is not hypothetical cost: during the 2026-07-25 OAuth
incident, the exact diagnostic lines written to classify session-refresh
failures (`refresh.cookie_absent` / `refresh.rejected` / `refresh.success`)
and session creation events were informational-level and therefore invisible,
forcing three separate defects to be diagnosed blind through request tracing
instead of logs.

The failure is silent in both directions: developers writing `logger.info(...)`
believe they are adding observability, and operators reading CloudWatch believe
the absence of those lines means the code path did not run. Both beliefs are
wrong today.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operator debugs a production incident from logs (Priority: P1)

An operator investigating a misbehaving backend function opens its CloudWatch
log group and sees the informational diagnostics the code emits (session
classification lines, state transitions, request outcomes) alongside the
warnings and errors that were already visible — enough to reconstruct what a
request did without resorting to X-Ray trace archaeology.

**Why this priority**: This is the incident-response gap that motivated the
feature. Every hour of blind debugging during an incident is directly
attributable to this story being unmet.

**Independent Test**: Trigger a known code path in the dashboard function that
emits an informational diagnostic (e.g., a session refresh), then confirm the
line appears in the function's CloudWatch log group within the normal log
delivery delay.

**Acceptance Scenarios**:

1. **Given** the deployed dashboard function, **When** a request executes a
   code path containing an informational log call in any backend module,
   **Then** that log line appears in the function's CloudWatch log group.
2. **Given** the deployed ingestion, analysis, and notification functions,
   **When** their scheduled or triggered work runs, **Then** informational
   log lines from their internal modules appear in their respective log groups.
3. **Given** an operator viewing logs during an incident, **When** they filter
   the log group for a request's identifier, **Then** informational and
   warning/error lines for that request are both present and distinguishable
   by severity.

---

### User Story 2 - Existing log consumers keep working (Priority: P2)

Anyone or anything that already consumes these logs — operators' saved
queries, the deploy pipeline's checks, alerting/metric rules, and the
already-visible warning/error lines — continues to work unchanged after the
fix ships.

**Why this priority**: A visibility fix that breaks existing alarms, breaks
warning-line greps, or floods the logs would trade one observability failure
for another. Compatibility is the guardrail on Story 1, not an optional
nicety.

**Independent Test**: Compare the set and shape of warning/error log lines,
structured JSON lines from the existing structured-logging paths, and any
metric-filter matches for a fixed workload before and after the change.

**Acceptance Scenarios**:

1. **Given** the pre-existing warning/error log output, **When** the fix is
   deployed, **Then** those lines still appear with unchanged severity
   semantics (no warnings lost, none demoted).
2. **Given** the existing structured JSON log lines (the dashboard service
   logger and the metrics module's structured output), **When** the fix is
   deployed, **Then** those lines continue to appear exactly once per event
   (no duplication, no wrapping that breaks their parseability).
3. **Given** any CloudWatch metric filters or alarms defined on these log
   groups, **When** the fix is deployed, **Then** they continue to match the
   events they matched before.

---

### User Story 3 - Log volume and cost stay bounded (Priority: P3)

The platform team can predict and bound the log volume increase: the
visibility floor is informational level (not debug), per-request log storms do
not appear, and the noisiest known emitters are reviewed so that turning on
informational logging does not multiply CloudWatch ingestion cost unexpectedly.

**Why this priority**: Cost and noise are real but secondary — a bounded
increase in log volume is an acceptable price for incident debuggability, and
the budget guardrail (~$60/month project-wide) has headroom for it only if the
increase is deliberate.

**Independent Test**: Measure log events per invocation for a representative
request on the dashboard function before and after; confirm debug-level lines
remain suppressed and the per-request increase is a bounded, reviewed number.

**Acceptance Scenarios**:

1. **Given** the fix is deployed, **When** a code path containing debug-level
   log calls executes, **Then** debug lines do NOT appear in the log group.
2. **Given** a representative dashboard request, **When** logs are counted
   per invocation after the change, **Then** the increase is attributable to
   intentional informational diagnostics, not accidental per-item loops.

---

### Edge Cases

- A module that already sets its own logger level explicitly (five handler
  entrypoints do today) must not be double-affected: its effective level must
  not become stricter, and its lines must not duplicate.
- The metrics module's structured logger attaches its own handler; the fix
  must not cause its events to emit twice (once via its handler, once via the
  root handler).
- Third-party library loggers (AWS SDK, HTTP clients, ML libraries) become
  visible at informational level too; the noisiest (e.g., HTTP request logs
  per call) could dominate volume — the fix must bound which loggers gain
  visibility or verify the noisy ones stay quiet.
- The streaming (SSE) function is explicitly out of scope: it uses a separate
  startup path that already enables informational logging, it has had zero
  invocations in over 30 days, and touching it is deferred by owner
  constraint. The fix must not require changes to it, and must not accidentally
  alter its behavior via shared modules.
- A future new Lambda added to the project should inherit the visibility fix
  by default rather than silently reverting to the dark-logger state
  (regression resistance).
- If log delivery configuration and code-level configuration disagree (one
  says informational, the other warning), the stricter one silently wins —
  the deployed combination must be verified end-to-end, not assumed from
  either half.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Informational-level log messages emitted by any backend module
  in the four batch/request Lambdas (dashboard, ingestion, analysis,
  notification) MUST be recorded in that function's CloudWatch log group.
- **FR-002**: Debug-level log messages MUST remain suppressed by default in
  all deployed environments.
- **FR-003**: Warning- and error-level log output that is visible today MUST
  remain visible with unchanged severity semantics.
- **FR-004**: Existing structured log lines (the dashboard service logger's
  JSON output and the metrics module's structured JSON output) MUST continue
  to be emitted exactly once per event and remain machine-parseable as they
  are today.
- **FR-005**: The change MUST NOT create new cloud resources; it may only
  modify configuration or code of existing functions and their delivery
  settings. (Standing owner constraint.)
- **FR-006**: The streaming (SSE) function MUST NOT require changes and MUST
  NOT change observable behavior as a result of this feature, including via
  modules it shares with other functions.
- **FR-007**: The visibility configuration MUST be applied through the
  project's normal delivery pipeline (infrastructure code and/or application
  code in git), not via console or one-off CLI mutation, so it survives
  redeploys and is visible in review. (Lesson from the frozen-env
  incidents: out-of-band configuration is a defect class in this project.)
- **FR-008**: Each of the four functions MUST have a verifiable post-deploy
  check demonstrating an informational line from a non-entrypoint module
  reaching its log group; the check for the dashboard function MUST be
  executable on demand (the other three may rely on their scheduled/triggered
  runs).
- **FR-009**: Log severity MUST remain distinguishable per line after the
  change (an operator can filter informational vs warning vs error).
- **FR-010**: Third-party library loggers MUST NOT gain unbounded
  informational verbosity: the change either scopes visibility to
  first-party modules or demonstrates that affected third-party loggers do
  not materially increase per-invocation log volume.
- **FR-011**: Modules and entrypoints that already configure their own
  logging levels MUST retain at least their current visibility (no
  regression to stricter levels, no duplicate emission).

### Key Entities

- **Log line**: A single recorded event with severity, timestamp, request
  correlation, and message; the unit operators filter and alarms match on.
- **Log group**: The per-function CloudWatch destination; the boundary at
  which visibility is verified.
- **Logger**: A named per-module emitter whose effective severity threshold
  decides whether a line is recorded; ~67 first-party module loggers exist,
  plus third-party library loggers.
- **Delivery configuration**: The function-level settings (format, level
  floor) that the platform applies before code-level configuration is
  consulted.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An informational diagnostic emitted by a non-entrypoint backend
  module appears in the dashboard function's log group within one deploy
  cycle of the fix landing (the original incident gap, closed).
- **SC-002**: 100% of the four in-scope functions show at least one
  informational line from a non-entrypoint module in their log group within
  one week of deploy (all four verified, not just dashboard).
- **SC-003**: Zero regressions in existing log consumers: no lost
  warning/error lines, no duplicated or malformed structured JSON events, no
  metric filter/alarm that stops matching (verified by before/after
  comparison on a fixed workload).
- **SC-004**: Debug-level lines remain absent from all four log groups
  post-deploy (spot-checked over one week of normal traffic).
- **SC-005**: Per-invocation log event count on a representative dashboard
  request increases by a bounded, reviewed amount, and monthly CloudWatch
  ingestion cost projection stays within the project's existing budget
  envelope (~$60/month total project spend).
- **SC-006**: The next incident's responder can classify a session-refresh
  failure from CloudWatch logs alone (the specific capability whose absence
  defined the 2026-07-25 incident experience).

## Assumptions

- The diagnosis of record (2026-07-26, live-evidence-backed): the darkness
  mechanism is the root logger's default WARNING threshold — the platform
  attaches a log handler but nothing sets the level, because the functions'
  delivery configuration specifies no application log level. Warning+ lines
  were always visible (488 stdlib warning events in a 48h window on the
  dashboard group; zero stdlib informational events). The fix design may rely
  on this mechanism.
- "Informational visibility" is defined at the log-group boundary: a line
  counts as visible only when it is queryable in CloudWatch, not when it is
  merely written by code.
- The five entrypoints that already self-configure levels (analysis,
  ingestion, notification, canary, chaos-restore handlers) and the metrics
  module's self-handled structured logger are existing behavior to preserve,
  not defects to fix here.
- Choosing between delivery-level configuration, code-level configuration, or
  structured-logging adoption (and any combination) is a planning decision;
  this spec constrains outcomes (FR-001..FR-011), not mechanism.
- Production functions follow the same fix through the normal pipeline;
  preprod is the verification environment.
