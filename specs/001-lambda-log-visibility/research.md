# Research: Lambda Log Visibility

**Date**: 2026-07-25 (diagnosis executed 2026-07-26 UTC)
**Inputs**: live-account diagnosis agent (CloudWatch + terraform + awslambdaric
source), Context7 powertools docs pull, local verification against installed
aws-lambda-powertools 3.23.0, AR#1 code inspection.

## R-1: Darkness mechanism (SETTLED — evidence, not theory)

**Decision basis**: `awslambdaric/bootstrap.py::_setup_logging` ALWAYS attaches
`LambdaLoggerHandler` to the root logger but calls `setLevel` ONLY when
`AWS_LAMBDA_LOG_LEVEL` holds a valid level name — which Lambda sets only when
the function's LoggingConfig has an `ApplicationLogLevel`. All deployed
functions have `LoggingConfig: {LogFormat: Text}` with no ApplicationLogLevel
and no LOG_LEVEL/POWERTOOLS_* env. Root therefore sits at Python default
WARNING; every un-leveled module logger inherits it.

**Live evidence**: 48h window on `/aws/lambda/preprod-sentiment-dashboard`:
488 stdlib `[WARNING]` events, 0 stdlib `[INFO]` events; 400-event sample =
282 platform, 104 powertools JSON, 14 stdlib WARNING. The incident's
"missing" lines were all `logger.info` (router_v2.py:742/757/762,
auth.py:197); the incident's visible "Token exchange failed" was
`logger.warning` (cognito.py:198) — consistent, no contradiction.

**Consequence**: the fix is a LEVEL problem, not a handler problem. Any
mechanism that sets the root level to INFO cures all first-party modules at
once; no handler/formatter work is needed or wanted.

## R-2: Per-function facts

| Function | Packaging | Startup logging config today | In scope |
|---|---|---|---|
| dashboard | image (lambda/python:3.13) | powertools Logger("dashboard") for request lines only; root untouched | YES |
| analysis | image | own module logger setLevel(INFO) at handler.py:78; log_structured() print-JSON channel | YES |
| ingestion | ZIP | own module logger setLevel(INFO) at handler.py:116 | YES |
| metrics | ZIP | NOTHING (no setLevel/basicConfig in handler) | YES (AR#1 add) |
| notification | ZIP | module logger from LOG_LEVEL env (unset→INFO) at handler.py:33 | YES |
| canary | ZIP | own module logger setLevel at handler.py:25 | YES (AR#1 add) |
| sse_streaming | image (python:3.13-slim, custom bootstrap, NO awslambdaric) | basicConfig(INFO) at handler.py:44-47 | NO (owner defer; already INFO) |
| chaos_restore | code only — NOT deployed (terraform TODO TD-2) | setLevel at handler.py:32 | NO (not deployed) |

Key subtlety: the five existing `setLevel` sites configure each handler's OWN
module logger, not root — which is why their entrypoint INFO appears while
their imported modules' INFO stays dark (verified live: ingestion handler
INFO visible + storage.py:184 INFO absent in the same invocation).

## R-3: ALC coupling (kills O1's "free lunch")

AWS constraint (powertools ALC docs + Lambda platform): `ApplicationLogLevel`
is only settable with `LogFormat=JSON`. JSON format re-shapes every emitted
line and wraps stdout free-text (powertools JSON, StructuredLogger JSON,
prints) in runtime JSON envelopes. Downstream: breaks the repo's single
Text-pattern metric filter `dashboard_import_errors`
(modules/monitoring/main.tf:30-41, feeding a CRITICAL alarm), and turns the
existing structured-JSON lines into nested JSON for their consumers.
Additionally `AWS_LAMBDA_LOG_LEVEL` outranks POWERTOOLS_LOG_LEVEL (documented
precedence), a coupling we'd carry forever after.

## R-4: powertools facts (verified against installed 3.23.0)

`aws_lambda_powertools.logging.utils.copy_config_to_registered_loggers(
source_logger, log_level=None, ignore_log_level=False, exclude=None,
include=None)` — exists at the canonical path (a Context7-indexed doc page
showed a different path; local import check settled it). It propagates the
powertools handler/level across `loggerDict`-registered loggers — the
sanctioned O3 building block. Powertools Logger does not touch root by
default. Log-buffering exists in 3.x but is opt-in (`logger_buffer=`);
irrelevant unless O3 chosen.

## R-5: Third-party logger reality check

botocore/urllib3: chatty at DEBUG, near-silent at INFO — NOT a risk.
httpx: logs one INFO line per request INCLUDING THE FULL URL; used by
finnhub.py, tiingo.py, cognito.py, hcaptcha.py. finnhub.py:127 passes the
API key as a URL query param (`params={"token": self.api_key}`) — root at
INFO without an httpx pin publishes the key to CloudWatch on every
ingestion poll. tiingo passes its key via headers (safe from URL logging).
→ FR-010 pins `httpx` and `httpcore` to WARNING inside the helper,
mechanism-independent.

## R-6: Mechanism decision

**Decision**: O2+ — shared `configure_lambda_logging()` helper (root
setLevel(INFO) + third-party pins + LOG_LEVEL override with INFO floor),
called by the six deployed entrypoints; FR-012 masking riders; coverage-guard
unit test.

**Rationale**: only option where the entire observable delta is "new INFO
lines appear" — Text format, every existing line, the metric filter, the
deploy grep, and the structured-JSON consumers survive byte-identical by
construction rather than by migration. Fewest moving parts 48h after a
7-defect incident; single-commit rollback. The helper centralizes what O2
naively scatters, and the coverage-guard test converts the "new Lambda
regresses" weakness into a CI-enforced invariant.

**Alternatives considered**:
- O1 terraform logging_config: rejected for the R-3 coupling; NOT zero-code
  anyway (httpx pin is code under every option). Signposted as the future
  migration if/when the project wants platform-level JSON + level control
  (also the only mechanism covering a Lambda that never calls the helper);
  revisit alongside any structured-logging initiative. (Per standing owner
  preference, this architecture decision is deferred as a signpost, not
  decided now.)
- O3 powertools propagation: correlation IDs are attractive but it inherits
  R-3's consumer migration PLUS a 71-logger propagation rewiring whose
  interaction with the metrics module's self-handled logger (R-7) and five
  self-leveling entrypoints multiplies verification surface. Deferred to the
  same signpost.
- O4 sweep: strictly dominated by O3.

**LoggingConfig version-scoping question** (was flagged for verification):
moot under O2 — no LoggingConfig change ships. Recorded for the signpost:
LoggingConfig is a function-level attribute (not version-pinned), so O1
would not be alias-trapped; the env-var trap (ignore_changes) is also
avoided by O2 since the helper needs no env var.

## R-7: FR-004 baseline unknown (must measure, not assume)

`src/lib/metrics.py` StructuredLogger attaches its own handler, sets INFO,
never sets `propagate=False`. Python logging dispatches a created record to
ALL ancestor handlers regardless of ancestor LOGGER levels — so its records
plausibly already emit twice (own handler + root LambdaLoggerHandler).
Whether they do is invisible in code (depends on runtime handler config) and
MUST be measured pre-deploy on the metrics log group. O2 does not change
record creation for this logger (its level is already INFO), so the correct
assertion is "no ADDITIONAL duplication vs baseline" (FR-004 as amended).

## R-8: Content-safety review targets (FR-012)

Newly-visible-line review is scoped to modules handling credentials/PII:
- notification/sendgrid_service.py:136,141 — full recipient email in
  currently-dark INFO → mask (e.g., `s***@domain`) in-change.
- shared/adapters/finnhub.py — covered by httpx pin; key-in-URL itself
  carded separately (hygiene, out of scope).
- Already-visible defect recorded not endorsed: notification/handler.py:56
  raw-event INFO dump (email + live magic-link token) — separate card;
  this feature must not widen it (it's entrypoint-level, already at INFO;
  root-level change does not affect it).
- dashboard/auth.py discipline confirmed good (8-char prefixes,
  sanitize_for_log, domain-only emails) — no edits needed.

AR#2 completion of the review record (FR-012/SC-007 require it recorded;
each verified REVIEWED, NO EXPOSURE):
- notification/digest_service.py:153,635,656 — dark INFO, logs counts and
  sanitized 8-char user ids only; PII-safe (and now notification's FR-008
  evidence line).
- shared/secrets.py:244 — "Secret retrieved from Secrets Manager", name-only,
  no value.
- shared/auth/cognito.py:157,312 — INFO lines, no values.
- Cross-repo grep for interpolated PII in INFO lines outside notification:
  no hits. Content verdict: clean beyond the already-recorded notification
  entrypoint defects (spec FR-012 records the full set incl. lines 170/220
  and error-path counterparts).

## R-9: Metric filter field-order discrepancy (AR#2 F8 — pre-existing)

The `dashboard_import_errors` filter pattern assumes field order `[time,
request_id, level=ERROR*, msg...]` but observed application lines lead with
`[LEVEL]`. If the filter never matched an application line, it has been dead
since authoring — a PRE-EXISTING defect, not a regression risk of this
feature. SC-003 verification includes a positive control (fire a synthetic
ImportModuleError-shaped line, watch the metric); outcome either proves the
filter alive (then Text preservation keeps it alive) or proves it
dead-on-arrival (then card its fix separately; this feature changes nothing
about it either way).

## R-10: SECOND masking layer found post-deploy — powertools SuppressFilter substring bug (2026-07-26)

Feature 001's own discriminating verification caught it: root=INFO went live
(C-8 visible) yet route-phase dashboard records still dropped.
`Logger(service="dashboard")` (handler.py) installs powertools'
`SuppressFilter("dashboard")` on every ROOT handler (logger.py:374-383,
powertools 3.23.0) to dedup its own propagated records — but
`SuppressFilter.filter` (filters.py:4-16) is a raw SUBSTRING test:
`"dashboard" in "src.lambdas.dashboard.router_v2"` → suppressed. Every
dashboard module logger was silenced at the root handler since that Logger
landed, INDEPENDENT of the root-level bug (two stacked masks). Deterministic
3/3 local repro with remove-filter control; awslambdaric and aws_xray_sdk
exonerated by source read. Fix: `_repair_powertools_suppress_filters()` in
the helper swaps it for a name-boundary filter (suppresses exactly
`dashboard` and `dashboard.*` — the documented intent); dashboard entrypoint
now calls the helper AFTER Logger() (the filter exists only post-init).
Upstream powertools issue worth filing.

## R-11: notification ZIP missing powertools + digest schedule dead (2026-07-26)

Notification E2E failure was a BROKEN DEPLOY, not dark loggers: its ZIP pip
list lacks aws-lambda-powertools while handler.py imports Tracer →
Runtime.ImportModuleError on every invoke (same class as metrics/1227).
Masked because the function has ZERO invocations in 7+ days — the hourly
digest EventBridge schedule evidently never fires (new card D). Pin added in
the follow-up PR.
