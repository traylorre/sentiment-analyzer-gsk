# Feature Specification: Lambda Log Visibility

**Feature Branch**: `001-lambda-log-visibility`
**Created**: 2026-07-25
**Status**: Draft
**Input**: User description: "Surface INFO-level application logs in CloudWatch across sentiment-analyzer Lambdas. All five preprod Lambdas have LoggingConfig LogFormat=Text with no ApplicationLogLevel, so the runtime attaches a root handler but never sets the root logger level; Python default WARNING applies and logger.info/debug from ~66 of 67 stdlib-logging modules under src/lambdas is silently dropped (WARNING+ was always visible). Three OAuth-incident bugs were debugged blind via X-Ray because the diagnostics were logger.info calls. Goal: INFO logs from all src/lambdas modules reach CloudWatch on dashboard, ingestion, analysis, notification Lambdas. SSE Lambda out of scope."

> Inventory correction (AR#1): the input's "five Lambdas / four in scope" was
> wrong. Terraform deploys SEVEN lambda modules; six are live non-SSE
> functions and all six are in scope. See Scope below.

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

## Scope

**In scope — the six deployed non-streaming functions** (all instantiate the
shared lambda terraform module; all use the standard runtime whose root-level
default causes the darkness): dashboard, ingestion, analysis, **metrics**,
notification, canary.

**Out of scope**: the streaming (SSE) function (separate startup path that
already enables informational logging; deferred by owner constraint; zero
invocations in 30+ days) and the chaos-restore handler (code exists but the
function is not deployed — terraform TODO TD-2).

## Clarifications

### Session 2026-07-25 (battleplan autonomy mode — self-answered from evidence; none deferred)

- Q: Which third-party loggers get pinned to WARNING (exact list vs open-ended
  policy)? → A: Exactly `httpx` and `httpcore` now. Evidence: research R-5 —
  httpx is the only third-party logger that emits at INFO per request (with
  full URL, the credential vector); botocore/urllib3 are DEBUG-chatty but
  INFO-quiet; the analysis Lambda's ML stack writes via stderr prints, not
  INFO logging. Policy: pin-on-evidence — the SC-004/SC-007 first-week
  queries are the detection mechanism for any logger that proves this wrong,
  and adding a pin is a one-line change to the helper.
- Q: What counts as the notification function's FR-008 evidence, given a
  real send would consume SendGrid quota (100/day) against a real recipient?
  → A (REVISED by AR#2 — the original premise "empty digest exercises only
  entrypoint INFO" was factually wrong): a synthetic empty-digest invoke
  (flat payload `{"notification_type": "digest"}`, accepted by the handler
  directly) DOES execute a genuinely dark non-entrypoint module —
  digest_service uses a bare un-leveled module logger and emits INFO on
  every run including empty ones ("Found users due for digest" count=0,
  "Digest processing complete"; both PII-safe). Notification's FR-008
  evidence = that digest_service line appearing post-deploy (it cannot
  appear pre-deploy), plus the unit-tested masked sendgrid_service line
  shape. No real email is sent; no test-mode send path exists or is needed.
- Q: SC-005's "bounded, reviewed amount" — what bound? → A: Guardrail: a
  representative dashboard request adds ≤10 new INFO lines (p50), and
  projected CloudWatch ingestion delta at current traffic is <$1/month.
  Evidence: the 48h diagnosis sample (400 events on the busiest group)
  puts absolute volumes so low that even a 3× multiplier is cents; the
  ≤10-line figure is verified during the FR-004 before/after comparison.
- Q: Does a deliberately set LOG_LEVEL=DEBUG env violate FR-002 ("DEBUG
  suppressed by default")? → A: No. Precedence: explicitly-set LOG_LEVEL
  (including DEBUG for temporary diagnostics) wins; unset → INFO floor.
  "By default" in FR-002 means the unset state. Evidence: this generalizes
  the existing notification pattern (handler.py:33 reads LOG_LEVEL, defaults
  INFO); contract C-1/C-2 already encode it, and the httpx/httpcore pins
  hold at WARNING regardless of LOG_LEVEL so the credential path stays
  closed even under DEBUG.

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
2. **Given** the other five in-scope functions, **When** their scheduled,
   triggered, or synthetically invoked work runs, **Then** informational log
   lines from their internal modules appear in their respective log groups.
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
structured JSON lines from the existing structured-logging paths, and the
known log-consumer inventory (below) for a fixed workload before and after
the change.

**Known log-consumer inventory** (established by AR#1 code inspection — this
is the complete acceptance set for compatibility):

1. The single log metric filter `dashboard_import_errors` on the dashboard
   log group — a Text-format, space-delimited pattern feeding a CRITICAL
   alarm. (The only artifact that structurally breaks if the log format
   flips to JSON.)
2. The deploy pipeline's post-deploy smoke grep of dashboard logs for
   import-error strings (case-insensitive substring match; format-tolerant).
3. Per-function error/duration alarms — metric-based, not log-pattern-based;
   unaffected by line shape.
4. The dashboard service logger's JSON lines and the metrics module's
   structured JSON output (machine-parsed by operators).

**Acceptance Scenarios**:

1. **Given** the pre-existing warning/error log output, **When** the fix is
   deployed, **Then** those lines still appear with unchanged severity
   semantics (no warnings lost, none demoted).
2. **Given** the existing structured JSON log lines, **When** the fix is
   deployed, **Then** those lines show no ADDITIONAL duplication or wrapping
   relative to the measured pre-deploy baseline (see FR-004 — the baseline
   itself must be measured, not assumed).
3. **Given** the log-consumer inventory above, **When** the fix is deployed,
   **Then** each consumer continues to match/parse the events it did before,
   or (if the chosen mechanism changes line format) has been migrated in the
   same change with before/after proof.

---

### User Story 3 - Log volume and content stay bounded and safe (Priority: P3)

The platform team can predict and bound the log volume increase, and — more
importantly — turning on informational visibility does not start recording
secrets or personal data that today's suppression was accidentally hiding.
The visibility floor is informational level (not debug), per-request log
storms do not appear, and every newly visible log call site in modules that
handle credentials or personal data is reviewed before enablement.

**Why this priority**: Cost and noise are real but secondary. Content safety
is not: this feature's entire effect is to make previously-invisible lines
visible, so any credential or PII sitting in a dark `logger.info` call
becomes a CloudWatch exposure the moment the feature ships. The review is the
feature's safety gate, not an optional audit.

**Independent Test**: Measure log events per invocation for a representative
request before and after; confirm debug-level lines remain suppressed; run
the newly-visible-call-site review and confirm zero credential/PII exposures
in the enabled output.

**Acceptance Scenarios**:

1. **Given** the fix is deployed, **When** a code path containing debug-level
   log calls executes, **Then** debug lines do NOT appear in the log group.
2. **Given** a representative dashboard request, **When** logs are counted
   per invocation after the change, **Then** the increase is attributable to
   intentional informational diagnostics, not accidental per-item loops.
3. **Given** the third-party HTTP client's per-request informational logging
   and the external-API adapter that passes its credential in the request
   URL, **When** the fix is enabled, **Then** no credential appears in any
   log group (the HTTP client's logger is pinned to warning-or-stricter, and
   the enablement review confirms it).
4. **Given** the notification module's currently-dark informational lines
   that include recipient email addresses, **When** the fix is enabled,
   **Then** those lines are masked or redacted before they become visible
   (personal data must not be newly exposed by this feature).

---

### Edge Cases

- A module that already sets its own logger level explicitly (analysis,
  ingestion, notification, canary entrypoints today; chaos-restore in code
  only) must not be double-affected: its effective level must not become
  stricter, and its lines must not duplicate.
- The metrics module's structured logger attaches its own handler and does
  not disable propagation — records plausibly reach both its handler and the
  root handler. Whether that already double-emits today is UNKNOWN; the
  pre-deploy baseline measurement (FR-004) must settle it before the
  after-state can be judged.
- The specific noisy third-party logger is the HTTP client (httpx), which
  logs one informational line per request including the full request URL —
  this is both the volume risk and the credential risk (one adapter passes
  its API key as a URL parameter). The AWS SDK and its transport are quiet at
  informational level (chatty only at debug) and are not the concern.
- The streaming (SSE) function is explicitly out of scope: it uses a separate
  startup path that already enables informational logging, it has had zero
  invocations in over 30 days, and touching it is deferred by owner
  constraint. The fix must not require changes to it, and must not
  accidentally alter its behavior via shared modules (several of its modules
  import shared code).
- If log delivery configuration and code-level configuration disagree (one
  says informational, the other warning), the stricter one silently wins —
  the deployed combination must be verified end-to-end against the
  alias-qualified live invocation path, not assumed from either half.
- Design note (non-normative): the most regression-resistant mechanism is one
  that lives where every function inherits it (all seven instantiate the same
  shared terraform module), so a future Lambda does not silently revert to
  the dark-logger state. If the chosen mechanism achieves this, verification
  is by inspection of the shared module; if not, this remains an accepted
  gap, documented in the plan.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Informational-level log messages emitted by any backend module
  in the six in-scope functions (dashboard, ingestion, analysis, metrics,
  notification, canary) MUST be recorded in that function's CloudWatch log
  group.
- **FR-002**: Debug-level log messages MUST remain suppressed by default in
  all deployed environments.
- **FR-003**: Warning- and error-level log output that is visible today MUST
  remain visible with unchanged severity semantics.
- **FR-004**: Structured log lines (the dashboard service logger's JSON
  output and the metrics module's structured JSON output) MUST show no
  additional duplication or format corruption relative to a pre-deploy
  baseline. The baseline (including whether the metrics module's structured
  logger already double-emits due to propagation) MUST be measured and
  recorded before the fix is enabled, not assumed.
- **FR-005**: The change MUST NOT create new cloud resources; it may only
  modify configuration or code of existing functions and their delivery
  settings. Modifying the existing log metric filter's pattern (if the
  chosen mechanism changes line format) is a permitted modification, not a
  new resource. (Standing owner constraint.)
- **FR-006**: The streaming (SSE) function MUST NOT require changes and MUST
  NOT change observable behavior as a result of this feature, including via
  modules it shares with other functions.
- **FR-007**: The visibility configuration MUST be applied through the
  project's normal delivery pipeline (infrastructure code and/or application
  code in git), not via console or one-off CLI mutation. Two project-specific
  traps MUST be respected: (a) the shared lambda module ignores drift on
  environment variables, so any environment-variable mechanism MUST go
  through the established CI wiring-script pattern rather than a terraform
  `environment` edit that will silently no-op; (b) live traffic invokes a
  pinned alias, so configuration applied to the unpublished version is not
  live until publish — verification MUST target the alias-qualified path.
- **FR-008**: Each of the six functions MUST have a verifiable post-deploy
  check demonstrating an informational line that CANNOT appear pre-deploy
  reaching its log group — i.e., a line from a currently-dark (un-leveled,
  non-entrypoint) logger. AR#2 established that canary and metrics contain
  NO such first-party line (canary imports no first-party modules; metrics'
  only INFO is its self-handled structured logger, visible today) — for
  them, the evidence line is the configuration helper's own self-test probe
  (one static INFO line per cold start on the helper's un-leveled child
  logger), which by construction can only appear when the fix is live.
  The dashboard check MUST be executable on demand;
  the other five MAY use scheduled runs (canary fires every 5 minutes) or a
  synthetic trigger — "wait for organic traffic" is not an acceptable
  verification plan for a function that may not organically emit for a week.
  Notification's accepted evidence is the three-part pair from
  Clarifications (synthetic-digest entrypoint INFO line + coverage-guard
  test + unit-tested masked line); no real email is sent for verification.
- **FR-009**: Log severity MUST remain distinguishable per line after the
  change (an operator can filter informational vs warning vs error).
- **FR-010**: Informational visibility MUST be scoped to first-party module
  loggers. The third-party loggers `httpx` and `httpcore` MUST be pinned to
  warning-or-stricter as part of this feature, and the pins MUST hold even
  under an explicit debug-level override (the credential path stays closed
  in every configuration). Pin list is exact per Clarifications (pin-on-
  evidence policy; first-week SC-004/SC-007 queries detect any needed
  additions). (AR#1 removed the former "or demonstrate no material volume
  increase" branch: it was satisfiable while leaking a credential at low
  volume.)
- **FR-011**: Modules and entrypoints that already configure their own
  logging LEVELS retain their current effective levels (no regression to
  stricter levels, no duplicate emission). This preservation covers level
  configuration ONLY — it does not endorse the CONTENT of existing log
  calls; known content defects are listed under FR-012 and carded, not
  protected.
- **FR-012** (content safety): Enabling informational visibility MUST NOT
  newly expose secrets, credentials, or personal data (CWE-312). Before
  enablement, every currently-dark informational call site in modules that
  handle credentials or personal data MUST be reviewed; identified exposures
  MUST be fixed or masked in the same change. Known cases from AR#1 that this
  requirement covers:
  - The external market-data adapter that passes its API key as a URL
    parameter, combined with the HTTP client's URL logging (blocked by
    FR-010's pin; the key-in-URL pattern itself is carded as separate
    hygiene).
  - The notification module's currently-dark lines logging full recipient
    email addresses (must be masked before they become visible).
  - Already-visible today and OUT of this feature's causal scope, but
    recorded so preservation is not misread as endorsement (all in the
    notification entrypoint, whose logger is INFO today): the raw invocation
    event dump (for magic-link events: recipient email + live sign-in
    token), and the full-recipient-email lines "Alert email sent to …" /
    "Magic link email sent to …" plus their error-path counterparts. These
    pre-existing CWE-312 defects MUST be carded as one fix; this feature
    MUST NOT widen them.

### Key Entities

- **Log line**: A single recorded event with severity, timestamp, request
  correlation, and message; the unit operators filter and alarms match on.
- **Log group**: The per-function CloudWatch destination; the boundary at
  which visibility is verified.
- **Logger**: A named per-module emitter whose effective severity threshold
  decides whether a line is recorded; 71 first-party modules create loggers
  (67 emit calls), plus third-party library loggers.
- **Delivery configuration**: The function-level settings (format, level
  floor) that the platform applies before code-level configuration is
  consulted.
- **Log consumer**: Anything that parses or matches recorded lines — the one
  metric filter, the deploy smoke grep, and human operators' queries.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An informational diagnostic emitted by a non-entrypoint backend
  module appears in the dashboard function's log group within one deploy
  cycle of the fix landing (the original incident gap, closed).
- **SC-002**: 100% of the six in-scope functions show at least one
  informational line from a non-entrypoint module in their log group within
  one week of deploy, using synthetic triggers where organic traffic does not
  exercise one (all six verified, not just dashboard).
- **SC-003**: Zero regressions across the named log-consumer inventory: no
  lost warning/error lines, no additional structured-JSON duplication versus
  the measured baseline, the metric filter still fires on its target
  pattern (migrated in-change if format changed), and the deploy smoke grep
  still matches. Verified by before/after comparison on a fixed workload.
- **SC-004**: Debug-level lines remain absent from all six log groups
  post-deploy (spot-checked over one week of normal traffic).
- **SC-005**: Per-invocation log event count on a representative dashboard
  request increases by ≤10 new informational lines (p50, measured in the
  FR-004 before/after comparison), and projected CloudWatch ingestion delta
  at current traffic is <$1/month — comfortably inside the project's
  ~$60/month budget envelope.
- **SC-006** (refresh-classification drill, replaces the former unfalsifiable
  "next incident" criterion): exercising all three session-refresh outcomes
  against preprod (cookie absent; cookie rejected; cookie valid) yields all
  three classification lines queryable in the dashboard log group. Testable
  the day the fix deploys.
- **SC-007** (content safety): the FR-012 review is executed and recorded;
  zero credentials and zero unmasked personal data appear in any of the six
  log groups attributable to newly visible lines (verified by targeted
  queries for the known-risk patterns during the first week).

## Assumptions

- The diagnosis of record (2026-07-25 local / 2026-07-26 UTC, live-evidence-
  backed): the darkness mechanism is the root logger's default WARNING
  threshold — the platform attaches a log handler but nothing sets the
  level, because the functions' delivery configuration specifies no
  application log level. Warning+ lines were always visible (48h dashboard
  window: 488 stdlib warning events, zero stdlib informational events —
  CloudWatch filter-log-events over `/aws/lambda/preprod-sentiment-dashboard`,
  patterns `[WARNING]` / `[INFO]`, run 2026-07-26 UTC during diagnosis; the
  query is re-runnable at plan time and the plan MUST re-record it). The fix
  design may rely on this mechanism.
- "Informational visibility" is defined at the log-group boundary: a line
  counts as visible only when it is queryable in CloudWatch, not when it is
  merely written by code.
- Mechanism choice is a planning decision, but AR#1 established it is NOT
  free: the delivery-configuration route (platform-level log level) is
  hard-coupled to JSON line format, which structurally breaks consumer #1
  (the Text-pattern metric filter) and risks double-encoding the existing
  structured JSON — choosing it obligates the in-change migration permitted
  by FR-005/SC-003. Code-level routes preserve Text format. The spec
  constrains outcomes (FR-001..FR-012) either way.
- Production functions follow the same fix through the normal pipeline;
  preprod is the verification environment.

## Adversarial Review #1

Independent refuter attacked the Stage-1 spec against the codebase and live
terraform (13 findings: 2 CRITICAL, 4 HIGH, 5 MEDIUM, 2 LOW). All CRITICAL
and HIGH findings resolved by spec edits in this revision; MEDIUM/LOW
resolved or absorbed as noted.

| # | Sev | Finding (compressed) | Resolution |
|---|-----|----------------------|------------|
| 1 | CRITICAL | FR-010's "no material volume increase" branch was satisfiable while leaking the Finnhub API key (key passed as URL param + httpx logs full URL at INFO; currently dark, this feature would light it) | FR-010 rewritten: first-party scoping mandatory, httpx pinned ≥ WARNING; new FR-012 content-safety requirement; US3 AC3; SC-007. Key-in-URL carded as separate hygiene |
| 2 | CRITICAL | Assumptions' "preserve existing behavior" clause codified the notification entrypoint's raw-event INFO dump (recipient email + live magic-link token, already visible today) as protected behavior | FR-011 narrowed to LEVEL preservation only; FR-012 lists the defect explicitly as carded-not-endorsed; feature must not widen it |
| 3 | HIGH | Function inventory wrong: 7 terraform lambda modules exist; metrics Lambda absent from spec entirely; canary deployed (5-min schedule) but excluded; chaos-restore listed but NOT deployed | New Scope section: six in-scope functions (adds metrics + canary); chaos-restore noted code-only; FR-001/008 + SC-002/004/007 updated to six |
| 4 | HIGH | Mechanism-neutrality false: platform ApplicationLogLevel requires JSON format → structurally breaks the one Text-pattern metric filter + double-encode risk on StructuredLogger | Assumption rewritten to state the coupling; FR-005 explicitly permits in-change filter migration; SC-003 requires migrated-with-proof if format changes |
| 5 | HIGH | FR-007 ignored two terraform traps: module ignores env drift (env-var mechanism would silently no-op) and live alias pins published versions (config on $LATEST isn't live) | FR-007 amended with both traps; FR-008/edge case require alias-qualified verification |
| 6 | HIGH | SC-002 "within one week" unfalsifiable for notification (hourly digest can run empty; non-entrypoint INFO may never fire organically) | FR-008 + SC-002 permit synthetic triggers; canary's 5-min schedule noted as evidence source |
| 7 | MEDIUM | SC-006 unfalsifiable ("next incident's responder…") | Replaced with the three-outcome refresh drill, testable at deploy |
| 8 | MEDIUM | FR-010 "materially" weasel word | Moot — branch deleted (finding 1) |
| 9 | MEDIUM | FR-004 asserted an unmeasured single-emission baseline (StructuredLogger never sets propagate=False; may double-emit TODAY) | FR-004 rephrased to measured-baseline + no-additional-duplication; edge case records the unknown |
| 10 | MEDIUM | Future-Lambda inheritance was aspiration dressed as requirement; shared-code bootstrap route collides with FR-006 (SSE imports shared modules) | Demoted to explicit non-normative design note favoring the shared-terraform-module locus; accepted-gap language if not achieved |
| 11 | MEDIUM | "Any metric filters or alarms" acceptance set undefined; spec never established the real inventory | US2 now embeds the complete verified inventory (1 metric filter, 1 deploy grep, metric-based alarms, structured-JSON parsers); SC-003 scoped to it |
| 12 | LOW | Third-party edge case misaimed (botocore/urllib3 quiet at INFO; the real risk is httpx, unnamed) | Edge case rewritten to name httpx; AWS-SDK scare dropped |
| 13 | LOW | Counts (67 vs 71 files), unverifiable 488/0 claim, Created date off by one | 71/67 both stated; evidence query documented + plan-time re-record required; date fixed to 2026-07-25 |

**Gate: 0 CRITICAL, 0 HIGH remaining.** Two follow-up cards spawned outside
this feature's scope (owner board): (a) notification entrypoint logs raw
magic-link event — pre-existing CWE-312, fix independently; (b) Finnhub
adapter passes API key as URL parameter — hygiene fix independent of logging.
