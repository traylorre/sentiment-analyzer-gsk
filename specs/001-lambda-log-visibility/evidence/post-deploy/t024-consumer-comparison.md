# T024 SC-003 Consumer Comparison (post-deploy)

Collected: 2026-07-29T13:54–14:10Z (UTC). Fix fully live since 2026-07-26 ~07:35Z
(deploy run 30192710400). AWS identity:
`arn:aws:iam::218795110243:user/sentiment-analyzer-preprod-deployer`, us-east-1.
Method identical to pre-deploy T002: `filter_log_events` per group, window widened
1h→6h→24h→72h→168h until >=50 events, most recent 50 kept. Raw samples:
`logshape-<fn>.json` in this directory (same schema as pre-deploy).

## 1. Shape classification (50 most recent events per group)

| function | window used | events | platform | structured JSON | stdlib [LEVEL] | stdlib tab-LEVEL | print/other |
|---|---|---|---|---|---|---|---|
| dashboard | 72h | 50 | 29 | 11 | 10 | 0 | 0 |
| ingestion | 1h | 50 | 10 | 0 | 40 | 0 | 0 |
| analysis | 24h | 50 | 12 | 13 | 23 | 0 | 2 |
| metrics | 1h | 50 | 29 | 0 | 21 | 0 | 0 |
| notification | 168h | 50 | 18 | 0 | 32 | 0 | 0 |
| canary | 1h | 50 | 15 | 0 | 35 | 0 | 0 |

Pre-deploy (for diff): dashboard 37/12/1/0/0, ingestion 13/0/37/0/0,
analysis 20/21/5/0/4, metrics 34/0/16/0/0, notification 0 events in 168h,
canary 15/0/35/0/0.

### Assertions

**Warning/error line shape unchanged — PASS.** All request-scoped stdlib lines still
follow `[LEVEL]\t<ts>\t<rid>\t<msg>`. Examples:

- pre: `[WARNING]\t2026-07-26T01:56:40.041Z\td13b124b-...\tJWT audience mismatch detected` (dashboard)
- post: `[WARNING]\t2026-07-29T02:48:09.114Z\t7bebdd52-...\tItem already analyzed, skipping` (analysis)
- post: `[ERROR]\t2026-07-26T07:04:53.496Z\t20438eeb-...\tFailed to query digest users` (notification)

Init-phase lines carry an empty request-id field (`[LEVEL]\t<ts>\t\t<msg>`) — still
the 4-field tab shape; the runtime has no request id during INIT. Not a shape change.

**Powertools JSON byte-shape identical — PASS.** Dashboard's pre-deploy keyset
(`cold_start, function_arn, function_memory_size, function_name, function_request_id,
level, location, message, method, path, service, timestamp, xray_trace_id`) appears
identically post-deploy. Analysis's three pre-deploy StructuredLogger keysets all
reappear unchanged. Additional keysets observed post-deploy (dashboard:
`{environment, level, location, message, service, table, timestamp}` and the powertools
core `{level, location, message, service, timestamp}`; analysis:
`{level, message, tickers_failed, tickers_written, timestamp}`) are different log
statements sampled in this window, same emitter patterns (powertools core keys /
StructuredLogger core keys) — not a format change.

**No wrapped/nested JSON — PASS.** 0 lines across all six groups where a JSON
`message` field contains JSON, or a `[LEVEL]` line wraps a `"level"`-keyed JSON body.

**Expected delta: new `[INFO]` stdlib lines — CONFIRMED.** stdlib line counts rose in
every group. The new lines are exactly the root-visibility class the feature intended:

- `[INFO]\t<ts>\t\tlogging configured: root INFO visibility active (feature 001)` (every group, init)
- `[INFO]\t<ts>\t<rid>\tFound credentials in environment variables.` (botocore, now visible)
- `[INFO]\t<ts>\t\tsuccessfully patched module sqlite3|botocore|requests` (aws_xray_sdk, analysis init)
- **notification** went from 0 events in 168h pre-deploy to a fully logging function
  (32 app lines in its most recent 50, incl. `[ERROR] ... Failed to query digest users`
  lines that were previously invisible).

Two side observations, recorded not judged:

1. Dashboard init emits a newly visible
   `[WARNING]\t<ts>\t\tCritical env var is empty or missing — feature may be degraded` —
   shape-conforming, previously suppressed; someone should eventually chase which var.
2. In the metrics group the runtime's `LAMBDA_WARNING: Unhandled exception...` text,
   which pre-deploy appeared as a bare line, now arrives wrapped as
   `[WARNING]\t<ts>\t\tLAMBDA_WARNING: ...`. Same text, now routed through the
   [LEVEL]-tab wrapper. No consumer greps for the bare form per the T002 survey.

## 2. FR-004 StructuredLogger duplication (metrics group)

**Verdict: STILL VACUOUS — the metrics Lambda never ran healthy post-deploy.**
The pre-deploy crash loop did not end on 07-26; it changed failure mode:

- Last `No module named 'aws_lambda_powertools'` error: **2026-07-26T05:15:14Z**
- First `No module named 'aws_xray_sdk'` error: **2026-07-26T05:15:57Z** (43s later)
- Last `aws_xray_sdk` error: **2026-07-29T14:03Z** (ongoing at collection time)
- Max gap between consecutive ImportModuleErrors since 07-26T00:00Z: ~1.2 min —
  no healthy window exists.
- Since 07-26T00:00Z: 15,484 START events; ImportModuleError module counts:
  `aws_lambda_powertools` 952, `aws_xray_sdk` 14,587.

Methodology (recorded as the go-forward baseline method): full-pagination
`filter_log_events` over the last 24h (30,324 events: 17,316 platform, 13,008 stdlib
`[LEVEL]`, **0 single-line JSON with a `level` key**); duplication tests (a) identical
JSON payload emitted 2+ times → 0 candidates, (b) JSON `message` re-emitted as a
stdlib text line within ±2s → 0 candidates. CloudWatch pattern `{ $.level = "*" }`
over 07-26T00:00Z→now: **0 events**. `src/lib/metrics.py` StructuredLogger still
never executes — the handler module now gets far enough to run the feature-001
logging config (`logging configured: root INFO visibility active` appears at init)
but dies importing `aws_xray_sdk`. Duplication count: N/A. Re-measure once the
packaging is fixed for real.

## 3. Positive control — metric filter `dashboard_import_errors`

**Verdict: FILTER STILL DEAD.** Live put-log-events control remains IAM-blocked
(not retried; pre-deploy denials in `filter-control.md` stand). Read-only evidence,
07-25→07-28 (and 07-22→now, daily period):

- `list-metrics --namespace SentimentAnalyzer/Packaging`: **empty** — the
  `DashboardImportErrors` metric still has never been created.
- `get-metric-statistics` DashboardImportErrors, hourly Sum 07-25→07-28: **no datapoints**.
- Meanwhile ~15,500 real `Runtime.ImportModuleError` events occurred in
  `/aws/lambda/preprod-sentiment-metrics` in that window. The filter caught none —
  though to be fair to the pattern, the filter only watches the **dashboard** group.
  This window therefore re-proves the coverage gap (the failing Lambda is unwatched);
  the field-position mismatch remains proven statically only (filter pattern
  unchanged: `[time, request_id, level=ERROR*, msg=...]`, verified via
  `describe-metric-filters` today).

## 4. Deploy smoke grep consumer

Runs 30192710400 (2026-07-26T07:23Z), 30283419540 (07-27T16:09Z), 30283936781
(07-27T16:16Z): all `success`, and each run's smoke steps individually succeeded
("Smoke Test Dashboard Lambda Imports", "Smoke Test SSE Lambda Imports", "Smoke Test
Analysis Lambda Imports", "Smoke Test (Post-Deployment)"). The new log shapes did not
break the smoke grep. Note: no smoke step covers the **metrics** Lambda's imports —
which is exactly how the `aws_xray_sdk` packaging regression shipped and stayed live
for 3+ days.

## Overall SC-003 verdict

**PASS** — all consumer-facing shapes (warning/error tab lines, powertools JSON key
sets, no nesting, smoke grep) are unchanged; the only delta is the intended new
`[INFO]` visibility. Separate defect, not an SC-003 failure: the metrics Lambda is
still crash-looping (now `aws_xray_sdk`), invisible to smoke tests and to the dead
import-error metric filter.
