# T003 FR-004 StructuredLogger Duplication Baseline (pre-deploy)

Collected: 2026-07-26T03:50:39Z (UTC), pre-deploy — log-visibility fix NOT yet deployed.
Log group: `/aws/lambda/preprod-sentiment-metrics`

## Query

boto3 `filter_log_events(logGroupName="/aws/lambda/preprod-sentiment-metrics",
startTime=now-24h)`, full pagination, no filter pattern.
Window: last 24h, **26,036 total events** (8,696 non-platform application/text lines,
0 single-line JSON lines).

Classification: single-line JSON with a `level` key = StructuredLogger/powertools-shaped;
`[LEVEL]`-prefixed = stdlib/runtime text. Planned duplication tests:
(a) identical JSON payload emitted 2+ times, (b) a JSON event's `message` re-emitted
as a stdlib-wrapped text line within +/-2s of the JSON line.

## Result: baseline VACUOUS — but not for lack of traffic

The metrics Lambda has plenty of traffic, but **every invocation fails at import**:

```
[ERROR] Runtime.ImportModuleError: Unable to import module 'handler': No module named 'aws_lambda_powertools'
```

- All application-shaped events in the 24h window are the crash pair
  (`LAMBDA_WARNING: Unhandled exception` + `Runtime.ImportModuleError`), repeating
  continuously.
- Structured JSON lines (CloudWatch pattern `{ $.level = "*" }`) in the last
  **7 days: 0**.
- Earliest `Runtime.ImportModuleError` in the 7-day window: 2026-07-19T03:52:01Z —
  that is the window boundary, so the crash loop is at least 7 days old, likely older.

`src/lib/metrics.py` StructuredLogger never executes because the handler never
imports. There are no logical events to count, so no ONCE/TWICE verdict is possible.

## Verdict

**Vacuous — re-measure at T024 (after deploy).** Duplication count: N/A
(0 StructuredLogger events in 7d). The code-path duplication risk is still real on
paper — StructuredLogger attaches its own JsonFormatter StreamHandler AND propagates
to the root logger (which in a working Lambda runtime carries the platform text
handler) — but it cannot be observed until the packaging failure is fixed.

## Side findings (feed R-9 / T005 and the feature premise)

1. The real runtime ImportModuleError line shape is
   `[ERROR] Runtime.ImportModuleError: <msg>` — no timestamp and no request-id fields
   between `[ERROR]` and the message. The metric filter in
   `infrastructure/terraform/modules/monitoring/main.tf:30-41` expects
   `[time, request_id, level=ERROR*, msg=...]` (level in field 3). Neither shape
   lines up with the filter.
2. This live, week-old ImportModuleError is in the **metrics** log group; the only
   import-error metric filter that exists watches the **dashboard** log group. No
   alarm has fired for a Lambda that has been 100% failing for 7+ days — consistent
   with this feature's premise.
